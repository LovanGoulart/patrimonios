const state={equipamentos:[],manutencoes:[],historico:[],lixeira:{equipamentos:[],manutencoes:[]},filter:'todos',current:null,scanner:null};
const $=id=>document.getElementById(id);

async function api(url,opt={}){
    const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opt});
    const d=await r.json().catch(()=>({}));
    if(r.status===401){window.location='/login';throw Error('Sessão expirada.')}
    if(!r.ok)throw Error(d.error||'Erro no servidor');
    return d;
}

function sync(d){
    state.equipamentos=d.equipamentos;
    state.manutencoes=d.manutencoes;
    state.historico=d.historico;
    updateStats();
    renderEquipamentos();
    renderManutencoes();
    renderBaixados();
    renderRecentActivities();
    renderLixeira();
}

function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}

document.addEventListener('DOMContentLoaded',async()=>{
    try{sync(await api('/api/bootstrap'))}catch(e){showToast(e.message,'error')}
    const hoje=new Date().toISOString().slice(0,10);
    ['maint-data','baixa-data','cad-data-aquisicao'].forEach(id=>{if($(id))$(id).value=hoje});
    if($('manual-barcode')) $('manual-barcode').addEventListener('keypress',e=>{if(e.key==='Enter')processManualBarcode()});
    // Verifica manutenções próximas a cada 5 minutos
    verificarManutencoesProximas();
    setInterval(verificarManutencoesProximas, 300000);
});

// ===== NAVEGAÇÃO =====
function switchTab(section){
    document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
    document.querySelectorAll('.nav-tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.footer-item').forEach(t=>t.classList.remove('active'));

    const sec=$('section-'+section);
    if(sec) sec.classList.add('active');

    const navTab=document.querySelector(`.nav-tab[data-section="${section}"]`);
    if(navTab) navTab.classList.add('active');

    const footTab=document.querySelector(`.footer-item[data-section="${section}"]`);
    if(footTab) footTab.classList.add('active');
    if(section==='lixeira') carregarLixeira();

    window.scrollTo({top:0,behavior:'smooth'});
}

async function refresh(){sync(await api('/api/bootstrap'))}

// ===== SCANNER =====
async function openScanner(){
    $('modal-scanner').classList.add('active');
    await initScanner();
}

async function initScanner(){
    if(state.scanner){try{await state.scanner.stop();await state.scanner.clear()}catch{}state.scanner=null}
    const reader=$('qr-reader');
    if(!reader) return;
    reader.innerHTML='';
    if(!window.isSecureContext){showToast('A câmera exige HTTPS ou localhost.','warning');return}
    if(!navigator.mediaDevices?.getUserMedia){showToast('Câmera não disponível neste navegador.','error');return}
    try{
        const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720}}});
        stream.getTracks().forEach(t=>t.stop());
        const s=document.createElement('div');
        s.style.cssText='padding:20px;text-align:center;color:#64748b';
        s.innerHTML='<b>Câmera autorizada.</b><br><small>Iniciando leitor de código…</small>';
        reader.appendChild(s);
        const script=document.createElement('script');
        script.src='https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js';
        script.onload=()=>startHtml5Scanner();
        script.onerror=()=>showToast('Não foi possível carregar o leitor. Use a entrada manual.','error');
        document.head.appendChild(script);
    }catch(e){showToast('Permissão de câmera negada: '+e.message,'error')}
}

function startHtml5Scanner(){
    if(!window.Html5Qrcode) return;
    const reader=$('qr-reader');
    if(!reader) return;
    reader.innerHTML='';
    state.scanner=new Html5Qrcode('qr-reader');
    state.scanner.start(
        {facingMode:'environment'},
        {fps:12,qrbox:{width:280,height:140},formatsToSupport:[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]},
        txt=>{closeScanner();processBarcode(txt)},
        ()=>{}
    ).catch(e=>showToast('Erro ao iniciar câmera: '+e,'error'));
}

async function closeScanner(){
    if(state.scanner){try{await state.scanner.stop();await state.scanner.clear()}catch{}state.scanner=null}
    const m=$('modal-scanner');
    if(m) m.classList.remove('active');
}

function switchToManual(){closeScanner();openManualEntry()}
function openManualEntry(){
    const mb=$('manual-barcode');
    if(mb){mb.value='';}
    const mm=$('modal-manual');
    if(mm){mm.classList.add('active');setTimeout(()=>mb&&mb.focus(),100)}
}

function processManualBarcode(){
    const b=$('manual-barcode');
    if(!b) return;
    const val=b.value.trim();
    if(!val) return showToast('Digite um código válido!','error');
    closeModal('modal-manual');
    processBarcode(val);
}

// ===== NOVO FLUXO: processBarcode mostra modal de ações =====
function processBarcode(barcode){
    const e=state.equipamentos.find(x=>x.barcode===barcode);
    state.current=e||{barcode};
    if(e){
        // Equipamento existe: mostra modal de ações
        showActionsModal(e);
    } else {
        // Novo equipamento: abre cadastro
        const cb=$('cad-barcode');
        if(cb) cb.value=barcode;
        const mc=$('modal-cadastro');
        if(mc) mc.classList.add('active');
        showToast('Novo equipamento detectado. Preencha os dados.','info');
    }
}

// ===== MODAL DE AÇÕES (após scan) =====
function showActionsModal(e){
    const nameEl=$('action-eq-name');
    const barcodeEl=$('action-eq-barcode');
    if(nameEl) nameEl.textContent=e.nome;
    if(barcodeEl) barcodeEl.textContent='Código: '+e.barcode;

    // Atualiza botões conforme status
    const grid=$('action-grid');
    if(grid){
        let html='';

        // Botão Ver Detalhes (sempre disponível)
        html+=`<button class="action-btn blue" onclick="actionVerDetalhes()">
            <div class="action-icon"><i class="fas fa-eye"></i></div>
            <div class="action-content">
                <div class="action-title">Ver Detalhes</div>
                <div class="action-desc">Visualizar histórico completo</div>
            </div>
        </button>`;

        // Botão Manutenção (somente se não estiver baixado)
        if(e.status!=='baixado'){
            html+=`<button class="action-btn green" onclick="actionRenovarManutencao()">
                <div class="action-icon"><i class="fas fa-tools"></i></div>
                <div class="action-content">
                    <div class="action-title">Enviar para Manutenção</div>
                    <div class="action-desc">Altera status para "Em Manutenção"</div>
                </div>
            </button>`;
        }

        // Botão Dar Baixa (somente se não estiver baixado)
        if(e.status!=='baixado'){
            html+=`<button class="action-btn orange" onclick="actionDarBaixa()">
                <div class="action-icon"><i class="fas fa-arrow-down"></i></div>
                <div class="action-content">
                    <div class="action-title">Dar Baixa</div>
                    <div class="action-desc">Remover equipamento do ativo</div>
                </div>
            </button>`;
        }

        // Botão Restaurar (se estiver em manutenção)
        if(e.status==='manutencao'){
            html+=`<button class="action-btn green" onclick="actionRestaurarAtivo()">
                <div class="action-icon"><i class="fas fa-check-circle"></i></div>
                <div class="action-content">
                    <div class="action-title">Restaurar para Ativo</div>
                    <div class="action-desc">Voltar status para "Ativo"</div>
                </div>
            </button>`;
        }

        grid.innerHTML=html;
    }

    const ma=$('modal-actions');
    if(ma) ma.classList.add('active');
}

// ===== AÇÕES =====
function actionRenovarManutencao(){
    closeModal('modal-actions');
    if(state.current&&state.current.id) openManutencaoRapida(state.current.id);
}
function actionDarBaixa(){
    closeModal('modal-actions');
    if(state.current&&state.current.id) openBaixa(state.current.id);
}
function actionVerDetalhes(){
    closeModal('modal-actions');
    if(state.current&&state.current.id) showDetalhes(state.current.id);
}

async function actionRestaurarAtivo(){
    closeModal('modal-actions');
    if(!state.current||!state.current.id) return;
    try{
        await api(`/api/equipamentos/${state.current.id}`,{method:'PUT',body:JSON.stringify({status:'ativo'})});
        await refresh();
        showToast('Equipamento restaurado para ativo!');
    }catch(e){showToast(e.message,'error')}
}

// ===== CADASTRO =====
async function salvarEquipamento(){
    const d={
        barcode:$('cad-barcode')?.value||'',
        nome:$('cad-nome')?.value.trim()||'',
        marca:$('cad-marca')?.value.trim()||'',
        modelo:$('cad-modelo')?.value.trim()||'',
        serie:$('cad-serie')?.value.trim()||'',
        categoria:$('cad-categoria')?.value||'',
        local:$('cad-local')?.value.trim()||'',
        responsavel:$('cad-responsavel')?.value.trim()||'',
        dataAquisicao:$('cad-data-aquisicao')?.value||'',
        valor:$('cad-valor')?.value||'',
        observacoes:$('cad-observacoes')?.value.trim()||''
    };
    if(!d.nome||!d.marca||!d.categoria||!d.local||!d.responsavel) return showToast('Preencha todos os campos obrigatórios!','error');
    try{
        await api('/api/equipamentos',{method:'POST',body:JSON.stringify(d)});
        closeModal('modal-cadastro');
        clearCadastroForm();
        await refresh();
        showToast('Equipamento cadastrado com sucesso!');
    }catch(e){showToast(e.message,'error')}
}

function clearCadastroForm(){
    ['cad-nome','cad-marca','cad-modelo','cad-serie','cad-local','cad-responsavel','cad-valor','cad-observacoes'].forEach(id=>{const el=$(id);if(el)el.value=''});
    const cc=$('cad-categoria'); if(cc) cc.value='';
    const cd=$('cad-data-aquisicao'); if(cd) cd.value=new Date().toISOString().slice(0,10);
}

// ===== MANUTENÇÃO RÁPIDA (após scan) =====
function openManutencaoRapida(id){
    state.current=state.equipamentos.find(e=>e.id===id);
    if(!state.current) return;
    const me=$('maint-rapida-equipamento');
    if(me) me.value=state.current.nome;
    const mm=$('modal-manutencao-rapida');
    if(mm) mm.classList.add('active');
}

async function salvarManutencaoRapida(){
    const d={
        tipo:'correctiva',
        data:new Date().toISOString().slice(0,10),
        tecnico:$('maint-rapida-tecnico')?.value.trim()||'',
        descricao:$('maint-rapida-descricao')?.value.trim()||'',
        custo:'',
        proximaManutencao:''
    };
    if(!d.tecnico||!d.descricao) return showToast('Preencha todos os campos obrigatórios!','error');
    if(!state.current||!state.current.id) return;
    try{
        // Primeiro registra a manutenção
        await api(`/api/equipamentos/${state.current.id}/manutencoes`,{method:'POST',body:JSON.stringify(d)});
        // Depois altera o status para manutenção
        await api(`/api/equipamentos/${state.current.id}`,{method:'PUT',body:JSON.stringify({status:'manutencao'})});
        closeModal('modal-manutencao-rapida');
        clearManutencaoRapidaForm();
        await refresh();
        showToast('Equipamento enviado para manutenção!','warning');
    }catch(e){showToast(e.message,'error')}
}

function clearManutencaoRapidaForm(){
    ['maint-rapida-tecnico','maint-rapida-descricao'].forEach(id=>{const el=$(id);if(el)el.value=''});
}

// ===== MANUTENÇÃO COMPLETA (via tela de detalhes) =====
function openManutencao(id){
    state.current=state.equipamentos.find(e=>e.id===id);
    if(!state.current) return;
    const me=$('maint-equipamento');
    if(me) me.value=state.current.nome;
    const mm=$('modal-manutencao');
    if(mm) mm.classList.add('active');
}

async function salvarManutencao(){
    const d={
        tipo:$('maint-tipo')?.value||'preventiva',
        data:$('maint-data')?.value||'',
        tecnico:$('maint-tecnico')?.value.trim()||'',
        descricao:$('maint-descricao')?.value.trim()||'',
        custo:$('maint-custo')?.value||'',
        proximaManutencao:$('maint-proxima')?.value||''
    };
    if(!d.data||!d.tecnico||!d.descricao) return showToast('Preencha todos os campos obrigatórios!','error');
    if(!state.current||!state.current.id) return;
    try{
        await api(`/api/equipamentos/${state.current.id}/manutencoes`,{method:'POST',body:JSON.stringify(d)});
        closeModal('modal-manutencao');
        clearManutencaoForm();
        await refresh();
        showToast('Manutenção registrada com sucesso!');
    }catch(e){showToast(e.message,'error')}
}

function clearManutencaoForm(){
    ['maint-tecnico','maint-descricao','maint-custo','maint-proxima'].forEach(id=>{const el=$(id);if(el)el.value=''});
    const mt=$('maint-tipo'); if(mt) mt.value='preventiva';
    const md=$('maint-data'); if(md) md.value=new Date().toISOString().slice(0,10);
}

// ===== BAIXA =====
function openBaixa(id){
    state.current=state.equipamentos.find(e=>e.id===id);
    if(!state.current) return;
    const be=$('baixa-equipamento');
    if(be) be.value=state.current.nome;
    const mb=$('modal-baixa');
    if(mb) mb.classList.add('active');
}

async function confirmarBaixa(){
    const d={
        motivo:$('baixa-motivo')?.value||'',
        data:$('baixa-data')?.value||'',
        responsavel:$('baixa-responsavel')?.value.trim()||'',
        observacoes:$('baixa-observacoes')?.value.trim()||''
    };
    if(!d.motivo||!d.data||!d.responsavel) return showToast('Preencha todos os campos obrigatórios!','error');
    if(!state.current||!state.current.id) return;
    try{
        await api(`/api/equipamentos/${state.current.id}/baixa`,{method:'POST',body:JSON.stringify(d)});
        closeModal('modal-baixa');
        clearBaixaForm();
        await refresh();
        showToast('Equipamento baixado com sucesso!','warning');
    }catch(e){showToast(e.message,'error')}
}

function clearBaixaForm(){
    ['baixa-responsavel','baixa-observacoes'].forEach(id=>{const el=$(id);if(el)el.value=''});
    const bm=$('baixa-motivo'); if(bm) bm.value='';
    const bd=$('baixa-data'); if(bd) bd.value=new Date().toISOString().slice(0,10);
}

// ===== DETALHES =====
async function showDetalhes(id){
    try{
        const d=await api(`/api/equipamentos/${id}`);
        state.current=d.equipamento;
        const eq=d.equipamento;
        const statusLabel={ativo:'Ativo',manutencao:'Em Manutenção',baixado:'Baixado'}[eq.status]||eq.status;
        let html=`<div class="detail-section"><h4><i class="fas fa-info-circle"></i> Informações Gerais</h4><div class="detail-grid">`;
        const fields=[['Código',eq.barcode],['Marca',eq.marca],['Modelo',eq.modelo],['Nº de Série',eq.serie],['Categoria',eq.categoria],['Local / Setor',eq.local],['Responsável',eq.responsavel],['Data de Aquisição',formatDateBR(eq.dataAquisicao)],['Valor (R$)',eq.valor],['Status',statusLabel],['Observações',eq.observacoes||'Nenhuma observação']];
        fields.forEach(x=>{
            html+=`<div class="detail-item ${x[0]==='Observações'?'full-width':''}"><div class="detail-label">${x[0]}</div><div class="detail-value">${esc(x[1])||'-'}</div></div>`;
        });
        html+=`</div></div>`;
        if(eq.baixa){
            html+=`<div class="detail-section"><h4><i class="fas fa-arrow-down"></i> Informações da Baixa</h4><div class="detail-grid">`;
            [['Motivo',eq.baixa.motivo],['Data',formatDateBR(eq.baixa.data)],['Responsável',eq.baixa.responsavel],['Observações',eq.baixa.observacoes]].forEach(x=>{
                html+=`<div class="detail-item"><div class="detail-label">${x[0]}</div><div class="detail-value">${esc(x[1])||'-'}</div></div>`;
            });
            html+=`</div></div>`;
        }
        if(d.manutencoes.length){
            html+=`<div class="detail-section"><h4><i class="fas fa-tools"></i> Histórico de Manutenções (${d.manutencoes.length})</h4>`;
            d.manutencoes.forEach(m=>{
                html+=`<div class="maintenance-card"><div class="maint-header"><span class="maint-type ${m.tipo}">${m.tipo==='preventiva'?'Preventiva':'Corretiva'}</span><span class="maint-date">${formatDateBR(m.data)}</span></div><div class="maint-desc">${esc(m.descricao)}</div><div class="maint-tech"><i class="fas fa-user"></i> ${esc(m.tecnico)} ${m.custo?'| R$ '+esc(m.custo):''}</div><div style="display:flex;justify-content:flex-end;margin-top:10px"><button class="maint-delete-btn" onclick="excluirManutencao(${m.id})" title="Excluir manutenção"><i class="fas fa-trash"></i> Excluir</button></div></div>`;
            });
            html+=`</div>`;
        }
        html+=`<div class="detail-section"><h4><i class="fas fa-history"></i> Linha do Tempo</h4><div class="timeline">`;
        d.historico.forEach(h=>{
            html+=`<div class="timeline-item ${h.acao}"><div class="timeline-date">${formatDateTimeBR(h.data)}</div><div class="timeline-title">${esc({cadastro:'Cadastro',manutencao:'Manutenção',baixa:'Baixa'}[h.acao]||h.acao)}</div></div>`;
        });
        html+=`</div></div>`;
        const dc=$('detalhes-content');
        if(dc) dc.innerHTML=html;
        const md=$('modal-detalhes');
        if(md) md.classList.add('active');
    }catch(e){showToast(e.message,'error')}
}

function editFromDetails(){closeModal('modal-detalhes');if(state.current&&state.current.id) openEditar(state.current.id)}

// ===== EDIÇÃO =====
function openEditar(id){
    const e=state.equipamentos.find(x=>x.id===id);
    if(!e) return;
    state.current=e;
    const cats=['Informática','Móveis','Eletrônicos','Máquinas e Ferramentas','Veículos','Equipamentos de Escritório','Outros'];
    let html=`<div class="form-group"><label>Código</label><input class="form-control" value="${esc(e.barcode)}" readonly></div>`;
    html+=`<div class="form-row"><div class="form-group"><label>Nome *</label><input class="form-control" id="edit-nome" value="${esc(e.nome)}"></div><div class="form-group"><label>Marca *</label><input class="form-control" id="edit-marca" value="${esc(e.marca)}"></div></div>`;
    html+=`<div class="form-row"><div class="form-group"><label>Modelo</label><input class="form-control" id="edit-modelo" value="${esc(e.modelo)}"></div><div class="form-group"><label>Nº de Série</label><input class="form-control" id="edit-serie" value="${esc(e.serie)}"></div></div>`;
    html+=`<div class="form-row-3"><div class="form-group"><label>Categoria *</label><select class="form-control" id="edit-categoria">${cats.map(x=>`<option ${x===e.categoria?'selected':''}>${x}</option>`).join('')}</select></div><div class="form-group"><label>Local *</label><input class="form-control" id="edit-local" value="${esc(e.local)}"></div><div class="form-group"><label>Responsável *</label><input class="form-control" id="edit-responsavel" value="${esc(e.responsavel)}"></div></div>`;
    html+=`<div class="form-row"><div class="form-group"><label>Data Aquisição</label><input type="date" class="form-control" id="edit-data-aquisicao" value="${e.dataAquisicao}"></div><div class="form-group"><label>Valor</label><input class="form-control" id="edit-valor" value="${esc(e.valor)}"></div></div>`;
    html+=`<div class="form-group"><label>Status</label><select class="form-control" id="edit-status"><option value="ativo" ${e.status==='ativo'?'selected':''}>Ativo</option><option value="manutencao" ${e.status==='manutencao'?'selected':''}>Em Manutenção</option><option value="baixado" ${e.status==='baixado'?'selected':''}>Baixado</option></select></div>`;
    html+=`<div class="form-group"><label>Observações</label><textarea class="form-control" id="edit-observacoes">${esc(e.observacoes)}</textarea></div>`;
    const ec=$('editar-content');
    if(ec) ec.innerHTML=html;
    const me=$('modal-editar');
    if(me) me.classList.add('active');
}

async function salvarEdicao(){
    const d={
        nome:$('edit-nome')?.value.trim()||'',
        marca:$('edit-marca')?.value.trim()||'',
        modelo:$('edit-modelo')?.value.trim()||'',
        serie:$('edit-serie')?.value.trim()||'',
        categoria:$('edit-categoria')?.value||'',
        local:$('edit-local')?.value.trim()||'',
        responsavel:$('edit-responsavel')?.value.trim()||'',
        dataAquisicao:$('edit-data-aquisicao')?.value||'',
        valor:$('edit-valor')?.value||'',
        status:$('edit-status')?.value||'',
        observacoes:$('edit-observacoes')?.value.trim()||''
    };
    if(!d.nome||!d.marca||!d.categoria||!d.local||!d.responsavel) return showToast('Preencha os campos obrigatórios!','error');
    if(!state.current||!state.current.id) return;
    try{
        await api(`/api/equipamentos/${state.current.id}`,{method:'PUT',body:JSON.stringify(d)});
        closeModal('modal-editar');
        await refresh();
        showToast('Equipamento atualizado!');
    }catch(e){showToast(e.message,'error')}
}

// ===== EXCLUSÃO / LIXEIRA =====
async function excluirEquipamento(id){
    const e=state.equipamentos.find(x=>x.id===id);
    if(!e) return;
    const ok=confirm(`Mover o equipamento "${e.nome}" para a lixeira?\n\nO equipamento e as manutenções vinculadas poderão ser restaurados depois.`);
    if(!ok) return;
    try{
        await api(`/api/equipamentos/${id}`,{method:'DELETE'});
        if(state.current?.id===id) state.current=null;
        await refresh();
        closeModal('modal-detalhes');
        showToast('Equipamento movido para a lixeira.','warning');
    }catch(e){showToast(e.message,'error')}
}

async function excluirManutencao(id){
    const m=state.manutencoes.find(x=>x.id===id);
    if(!m) return;
    const ok=confirm(`Mover esta manutenção de "${m.equipamentoNome}" para a lixeira?\n\nEla poderá ser restaurada depois.`);
    if(!ok) return;
    try{
        await api(`/api/manutencoes/${id}`,{method:'DELETE'});
        await refresh();
        if(state.current?.id===m.equipamentoId && document.getElementById('modal-detalhes')?.classList.contains('active')) await showDetalhes(m.equipamentoId);
        showToast('Manutenção movida para a lixeira.','warning');
    }catch(e){showToast(e.message,'error')}
}

async function carregarLixeira(){
    try{
        const d=await api('/api/lixeira');
        state.lixeira=d;
        renderLixeira();
    }catch(e){showToast(e.message,'error')}
}

async function restaurarEquipamento(id){
    const e=state.lixeira.equipamentos.find(x=>x.id===id);
    if(!e) return;
    if(!confirm(`Restaurar o equipamento "${e.nome}"?\n\nAs manutenções que foram excluídas junto com ele também serão restauradas.`)) return;
    try{ await api(`/api/lixeira/equipamentos/${id}/restaurar`,{method:'POST'}); await refresh(); await carregarLixeira(); showToast('Equipamento restaurado com sucesso!','success'); }
    catch(e){showToast(e.message,'error')}
}

async function restaurarManutencao(id){
    const m=state.lixeira.manutencoes.find(x=>x.id===id);
    if(!m) return;
    if(!confirm(`Restaurar esta manutenção de "${m.equipamentoNome}"?`)) return;
    try{ await api(`/api/lixeira/manutencoes/${id}/restaurar`,{method:'POST'}); await refresh(); await carregarLixeira(); showToast('Manutenção restaurada com sucesso!','success'); }
    catch(e){showToast(e.message,'error')}
}

async function excluirDefinitivamenteEquipamento(id){
    const e=state.lixeira.equipamentos.find(x=>x.id===id);
    if(!e) return;
    if(!confirm(`APAGAR DEFINITIVAMENTE "${e.nome}"?\n\nEsta ação não poderá ser desfeita e também apagará as manutenções vinculadas.`)) return;
    try{ await api(`/api/lixeira/equipamentos/${id}`,{method:'DELETE'}); await carregarLixeira(); showToast('Equipamento apagado definitivamente.','success'); }
    catch(e){showToast(e.message,'error')}
}

async function excluirDefinitivamenteManutencao(id){
    const m=state.lixeira.manutencoes.find(x=>x.id===id);
    if(!m) return;
    if(!confirm('APAGAR DEFINITIVAMENTE esta manutenção?\n\nEsta ação não poderá ser desfeita.')) return;
    try{ await api(`/api/lixeira/manutencoes/${id}`,{method:'DELETE'}); await carregarLixeira(); showToast('Manutenção apagada definitivamente.','success'); }
    catch(e){showToast(e.message,'error')}
}

function renderLixeira(){
    const el=$('lixeira-list');
    if(!el) return;
    const eq=state.lixeira.equipamentos||[], ms=state.lixeira.manutencoes||[];
    const total=eq.length+ms.length;
    const count=$('nav-count-lixeira'); if(count) count.textContent=total;
    if(!total){el.innerHTML=`<div class="empty-state"><div class="empty-icon">🗑️</div><h3>Lixeira vazia</h3><p>Itens excluídos aparecerão aqui e poderão ser recuperados.</p></div>`;return;}
    let html='';
    if(eq.length){
        html+=`<div class="trash-group"><h3><i class="fas fa-desktop"></i> Equipamentos (${eq.length})</h3>`;
        html+=eq.map(e=>`<div class="trash-card"><div class="trash-icon"><i class="fas fa-box"></i></div><div class="trash-info"><b>${esc(e.nome)}</b><div>${esc(e.marca)}${e.modelo?' · '+esc(e.modelo):''}</div><small>Patrimônio: ${esc(e.barcode)} · Excluído em ${formatDateTimeBR(e.excluidoEm)}</small></div><div class="trash-actions"><button class="btn btn-success btn-sm" onclick="restaurarEquipamento(${e.id})"><i class="fas fa-rotate-left"></i> Restaurar</button><button class="btn btn-danger btn-sm" onclick="excluirDefinitivamenteEquipamento(${e.id})"><i class="fas fa-trash"></i> Apagar</button></div></div>`).join('');
        html+='</div>';
    }
    if(ms.length){
        html+=`<div class="trash-group"><h3><i class="fas fa-tools"></i> Manutenções (${ms.length})</h3>`;
        html+=ms.map(m=>`<div class="trash-card"><div class="trash-icon"><i class="fas fa-wrench"></i></div><div class="trash-info"><b>${esc(m.equipamentoNome)}</b><div>${m.tipo==='preventiva'?'Preventiva':'Corretiva'} · ${formatDateBR(m.data)} · ${esc(m.tecnico)}</div><small>${m.excluidoComEquipamento?'Excluída junto com o equipamento':'Excluída individualmente'} · ${formatDateTimeBR(m.excluidoEm)}</small></div><div class="trash-actions">${m.excluidoComEquipamento?'<span class="trash-note">Restaura com o equipamento</span>':`<button class="btn btn-success btn-sm" onclick="restaurarManutencao(${m.id})"><i class="fas fa-rotate-left"></i> Restaurar</button>`}<button class="btn btn-danger btn-sm" onclick="excluirDefinitivamenteManutencao(${m.id})"><i class="fas fa-trash"></i> Apagar</button></div></div>`).join('');
        html+='</div>';
    }
    el.innerHTML=html;
}

// ===== RENDERIZAÇÃO =====
function dataEquipamento(e){
    const t=e.dataAquisicao ? Date.parse(e.dataAquisicao+'T00:00:00') : NaN;
    return Number.isNaN(t) ? 0 : t;
}

function ordenarEquipamentos(a){
    const prioridade={manutencao:0,ativo:1,baixado:2};
    return [...a].sort((x,y)=>{
        const px=prioridade[x.status] ?? 3;
        const py=prioridade[y.status] ?? 3;
        if(px!==py) return px-py;
        const dx=dataEquipamento(x), dy=dataEquipamento(y);
        if(dx!==dy) return dy-dx;
        return (y.id||0)-(x.id||0);
    });
}

function renderEquipamentos(){
    const s=($('search-equipamentos')?.value||'').toLowerCase();
    let a=state.equipamentos.filter(e=>(state.filter==='todos'||e.status===state.filter)&&[e.nome,e.marca,e.barcode,e.local,e.responsavel].some(v=>String(v).toLowerCase().includes(s)));
    a=ordenarEquipamentos(a);
    const el=$('equipamentos-list');
    if(!el) return;
    el.innerHTML=a.length?a.map(card).join(''):`<div class="empty-state"><div class="empty-icon">📦</div><h3>Nenhum equipamento encontrado</h3><p>Escaneie um código ou digite manualmente.</p></div>`;
}

function card(e){
    const icon={'Informática':'fa-laptop','Móveis':'fa-couch','Eletrônicos':'fa-tv','Máquinas e Ferramentas':'fa-cogs','Veículos':'fa-car','Equipamentos de Escritório':'fa-print','Outros':'fa-box'}[e.categoria]||'fa-box';
    return `<div class="equipment-card" onclick="showDetalhes(${e.id})"><div class="eq-icon" style="background:var(--primary-light);color:var(--primary)"><i class="fas ${icon}"></i></div><div class="eq-info"><div class="eq-name">${esc(e.nome)}</div><div class="eq-meta"><span>▦ ${esc(e.barcode)}</span><span>⌂ ${esc(e.local)}</span><span>👤 ${esc(e.responsavel)}</span></div></div><span class="eq-status status-${e.status}">${e.status==='ativo'?'Ativo':e.status==='manutencao'?'Em Manutenção':'Baixado'}</span><div class="eq-actions" onclick="event.stopPropagation()"><button class="btn-edit" onclick="openEditar(${e.id})"><i class="fas fa-edit"></i></button>${e.status!=='baixado'?`<button class="btn-maint" onclick="openManutencao(${e.id})"><i class="fas fa-tools"></i></button><button class="btn-delete" onclick="openBaixa(${e.id})" title="Dar baixa"><i class="fas fa-arrow-down"></i></button>`:''}<button class="btn-trash" onclick="excluirEquipamento(${e.id})" title="Excluir definitivamente"><i class="fas fa-trash"></i></button></div></div>`;
}

function renderManutencoes(){
    const s=($('search-manutencoes')?.value||'').toLowerCase();
    const a=state.manutencoes.filter(m=>(m.equipamentoNome+' '+m.tecnico+' '+m.descricao).toLowerCase().includes(s));
    const ml=$('manutencoes-list');
    if(!ml) return;
    ml.innerHTML=a.length?a.map(m=>{
        const eq=state.equipamentos.find(e=>e.id===m.equipamentoId);
        const clickable=eq?`onclick="showDetalhes(${m.equipamentoId})" style="cursor:pointer"`:'style="cursor:default"';
        return `<div class="maintenance-card" ${clickable}><div class="maint-header"><span class="maint-type ${m.tipo}">${m.tipo==='preventiva'?'Preventiva':'Corretiva'}</span><span class="maint-date">${formatDateBR(m.data)}</span></div><b>${esc(m.equipamentoNome)}</b><div class="maint-desc">${esc(m.descricao)}</div><div class="maint-tech">👤 ${esc(m.tecnico)} ${m.custo?'| R$ '+esc(m.custo):''}${m.proximaManutencao?` | 📅 Próxima: ${formatDateBR(m.proximaManutencao)}`:''}</div><div style="display:flex;justify-content:flex-end;margin-top:10px" onclick="event.stopPropagation()"><button class="maint-delete-btn" onclick="excluirManutencao(${m.id})" title="Excluir manutenção"><i class="fas fa-trash"></i> Excluir</button></div></div>`;
    }).join(''):`<div class="empty-state"><h3>Nenhuma manutenção registrada</h3></div>`;
}

function renderBaixados(){
    const s=($('search-baixados')?.value||'').toLowerCase();
    const a=state.equipamentos.filter(e=>e.status==='baixado'&&(e.nome+' '+e.marca+' '+e.barcode).toLowerCase().includes(s));
    const bl=$('baixados-list');
    if(!bl) return;
    bl.innerHTML=a.length?a.map(card).join(''):`<div class="empty-state"><h3>Nenhum equipamento baixado</h3></div>`;
}

function renderRecentActivities(){
    const ra=$('recent-activities');
    if(!ra) return;
    ra.innerHTML=state.historico.slice(0,10).map(h=>{
        const e=state.equipamentos.find(x=>x.id===h.equipamentoId);
        return `<div style="display:flex;gap:14px;padding:14px 0;border-bottom:1px solid var(--gray-100)"><div style="font-size:22px">${h.acao==='cadastro'?'➕':h.acao==='manutencao'?'🔧':'⬇️'}</div><div><b>${esc({cadastro:'Cadastro',manutencao:'Manutenção',baixa:'Baixa'}[h.acao])}: ${esc(e?.nome||'Equipamento')}</b><div style="font-size:12px;color:var(--gray-400)">${formatDateTimeBR(h.data)}</div></div></div>`;
    }).join('')||`<div class="empty-state"><h3>Nenhuma atividade recente</h3></div>`;
}

function updateStats(){
    const a=state.equipamentos;
    const st=$('stat-total'); if(st) st.textContent=a.length;
    const sa=$('stat-ativo'); if(sa) sa.textContent=a.filter(e=>e.status==='ativo').length;
    const sm=$('stat-manutencao'); if(sm) sm.textContent=a.filter(e=>e.status==='manutencao').length;
    const sb=$('stat-baixado'); if(sb) sb.textContent=a.filter(e=>e.status==='baixado').length;
    const smt=$('stat-manutencoes-total'); if(smt) smt.textContent=state.manutencoes.length;
    const nce=$('nav-count-eq'); if(nce) nce.textContent=a.filter(e=>e.status!=='baixado').length;
    const ncm=$('nav-count-maint'); if(ncm) ncm.textContent=state.manutencoes.length;
    const ncb=$('nav-count-baixa'); if(ncb) ncb.textContent=a.filter(e=>e.status==='baixado').length;
}

// ===== FILTROS =====
function filterStatus(s){state.filter=s;document.querySelectorAll('.filter-tab').forEach(t=>t.classList.remove('active'));if(event&&event.target)event.target.classList.add('active');renderEquipamentos()}
function filterEquipamentos(){renderEquipamentos()}
function filterManutencoes(){renderManutencoes()}
function filterBaixados(){renderBaixados()}

// ===== UTILITÁRIOS =====
function closeModal(id){const m=$(id); if(m) m.classList.remove('active');}
function formatCurrency(i){let v=i.value.replace(/\D/g,'');i.value=(v/100).toFixed(2).replace('.',',').replace(/\B(?=(\d{3})+(?!\d))/g,'.')}
function formatDateBR(s){if(!s)return '';const [a,m,d]=s.split('-');return `${d}/${m}/${a}`}
function formatDateTimeBR(s){return s?new Date(s).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}):''}

function showToast(message,type='success'){
    const c=$('toast-container');
    if(!c) return;
    const t=document.createElement('div');
    t.className='toast '+type;
    const titles={error:'Erro!',warning:'Atenção!',info:'Informação!',success:'Sucesso!'};
    const icons={error:'fa-exclamation-circle',warning:'fa-exclamation-triangle',info:'fa-info-circle',success:'fa-check-circle'};
    t.innerHTML=`<div class="toast-icon"><i class="fas ${icons[type]||icons.success}"></i></div><div class="toast-content"><div class="toast-title">${titles[type]||titles.success}</div><div class="toast-message">${esc(message)}</div></div>`;
    c.appendChild(t);
    setTimeout(()=>t.remove(),4500);
}

// ===== NOTIFICAÇÕES DE MANUTENÇÃO =====
let notificacoesManutencao = JSON.parse(localStorage.getItem('patrimonio_notificacoes')||'[]');

async function verificarManutencoesProximas(){
    try{
        const d=await api('/api/manutencoes/proximas');
        if(!d.proximas||!d.proximas.length) return;
        const hoje=new Date().toISOString().slice(0,10);
        d.proximas.forEach(m=>{
            const chave=`${hoje}-${m.id}`;
            if(notificacoesManutencao.includes(chave)) return;
            const msg=m.diasRestantes<=0?`⚠️ Manutenção de "${esc(m.equipamentoNome)}" venceu hoje!`:`📅 Manutenção de "${esc(m.equipamentoNome)}" vence em ${m.diasRestantes} dia(s)`;
            showToast(msg,'warning');
            notificacoesManutencao.push(chave);
        });
        const limite=new Date(); limite.setDate(limite.getDate()-7);
        notificacoesManutencao=notificacoesManutencao.filter(k=>{
            const data=k.split('-')[0];
            return new Date(data)>=limite;
        });
        localStorage.setItem('patrimonio_notificacoes',JSON.stringify(notificacoesManutencao));
    }catch(e){/*silencioso*/}
}

function limparNotificacoesManutencao(){
    notificacoesManutencao=[];
    localStorage.removeItem('patrimonio_notificacoes');
}

function exportData(){window.location='/api/export'}