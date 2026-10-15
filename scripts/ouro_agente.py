"""O agente faz o trabalho; usuário decide. Casos sintéticos, sem API paga."""
import copy
from fintips import triagem_universal as t
from fintips import triagem_agente as a

def gerar():
    b=t.vazio();hoje='2026-10-15'
    ds=[{'id':'plan-local','tipo':'plano','campos':{'titulo':'Quero ler mais CANARY','atributo':'INT'},'acao':'criar','porque':'Pedido sintético'},
        {'id':'book-local','tipo':'livro','campos':{'titulo':'Estou lendo “BOOK_CANARY” 3 dias por semana e já li 25%'},'acao':'criar','porque':'Pedido sintético'}]
    ctx=a.contexto(b,ds,hoje)
    def v(field,owner='rascunho_1',papel=None):return next(r['ref'] for r in ctx['publico']['valores_disponiveis'] if r['campo']==field and r['dono']==owner and (papel is None or r['papel']==papel))
    response={'registros':[{'ref':'rascunho_1','tipo':'livro','campos':[{'campo':'titulo','valor':v('titulo',papel='titulo_curto')},{'campo':'dias_semana','valor':v('dias_semana')},{'campo':'progresso_bp','valor':v('progresso_bp')}]}],
        'relacoes':[{'de':'rascunho_1','para':'rascunho_0','tipo':'apoia'}],'pergunta':None}
    cases=[]
    def add(name,op,i):
        if isinstance(i.get('resposta',{}).get('pergunta'),dict):i['resposta']['pergunta'].setdefault('texto','Qual área faz sentido para {{rascunho_0}}?')
        cases.append({'nome':name,'operacao':op,'entrada':i,'resultado':t.executar(op,i)})
    base={'bundle':b,'rascunhos':ds,'hoje':hoje}
    add('projeção sem texto, com referências e semântica fechada','triagem.agente_contexto',base)
    add('pedido limitado e gerado a partir da fonte local','triagem.agente_pedido',base)
    add('agente preenche três campos e correlaciona sem cliques por campo','triagem.agente_aplicar',{**base,'resposta':response})
    fresh=copy.deepcopy(response);fresh['registros']=[{'ref':'novo_0','tipo':'objetivo','campos':[{'campo':'titulo','valor':v('titulo',papel='titulo_curto')},{'campo':'atributo','valor':v('atributo','rascunho_0')}]}];fresh['relacoes']=[{'de':'novo_0','para':'rascunho_1','tipo':'relacionado'}]
    add('agente cria asset adicional e vínculo via contrato universal','triagem.agente_aplicar',{**base,'resposta':fresh})
    missing=copy.deepcopy(base);missing['rascunhos'][0]['campos'].pop('atributo')
    add('modelo esquece pergunta: aparelho recupera obrigatório','triagem.agente_aplicar',{**missing,'resposta':{'registros':[],'relacoes':[],'pergunta':None}})
    private=copy.deepcopy(base);private['rascunhos'].append({'id':'money-local','tipo':'compromisso','campos':{'titulo':'SERVICE_CANARY','valor_centavos':12345,'origem_real':'ORIGIN_CANARY','destino_real':'DEST_CANARY'},'acao':'criar','porque':'Pedido sintético'})
    add('origem e destino não viram referências nem metadados','triagem.agente_contexto',private)
    existing=t.aplicar(b,t.preparar(b,[ds[0]],[],'base-existing'),True,hoje,1792065600000)['bundle']
    add('duplicata exata e única atualiza sem pedir operação de cadastro','triagem.agente_aplicar',{'bundle':existing,'rascunhos':ds,'hoje':hoje,'resposta':response})
    separated=copy.deepcopy(ds);separated[0]['porque']='Registro separado por escolha explícita da pessoa na conversa.'
    add('escolha explícita de manter separado prevalece sobre deduplicação','triagem.agente_aplicar',{'bundle':existing,'rascunhos':separated,'hoje':hoje,'resposta':response})
    inherited=copy.deepcopy(ds);inherited[0]['campos'].pop('atributo')
    add('duplicata reaproveita área existente e dispensa pergunta redundante','triagem.agente_aplicar',{'bundle':existing,'rascunhos':inherited,'hoje':hoje,'resposta':{'registros':[],'relacoes':[],'pergunta':{'ref':'rascunho_0','campo':'atributo'}}})
    natural=copy.deepcopy(ds);natural[1]['tipo']='plano';natural[1]['campos']={'titulo':'Quero ler DUNA_CANARY 3 dias por semana'}
    nc=a.contexto(b,natural,hoje)
    def nv(field,owner,papel):return next(v['ref'] for v in nc['publico']['valores_disponiveis'] if v['dono']==owner and v['campo']==field and v['papel']==papel)
    nr={'registros':[{'ref':'rascunho_1','tipo':'livro','campos':[{'campo':'titulo','valor':nv('titulo','rascunho_1','titulo_curto')},{'campo':'dias_semana','valor':nv('dias_semana','rascunho_1','extraido')}]},
        {'ref':'novo_0','tipo':'tarefa','campos':[{'campo':'titulo','valor':nv('titulo','rascunho_1','acao_leitura')},{'campo':'inicio','valor':nv('inicio','catalogo','padrao_hoje')},{'campo':'repetir','valor':nv('repetir','catalogo','padrao')},{'campo':'atributo','valor':nv('atributo','rascunho_0','campo')}]}],
        'relacoes':[{'de':'novo_0','para':'rascunho_1','tipo':'apoia'}],'pergunta':None}
    add('sem aspas nem seleção de tipo: agente prepara livro e tarefa relacionados','triagem.agente_aplicar',{'bundle':b,'rascunhos':natural,'hoje':hoje,'resposta':nr})
    question=copy.deepcopy(base)
    question['rascunhos'][0]['campos'].pop('atributo')
    add('pergunta natural do agente restaura o nome só no aparelho','triagem.agente_aplicar',{**question,'resposta':{'registros':[],'relacoes':[],'pergunta':{'ref':'rascunho_0','campo':'atributo','texto':'Para {{rascunho_0}}, qual área você quer priorizar?'}}})
    negated=copy.deepcopy(base);negated['rascunhos'][0]['campos']['titulo']='Não quero treinar com PRIVATE_PERSON_CANARY; se puder, quero ler'
    add('estrutura preserva negação e condição sem publicar texto','triagem.agente_contexto',negated)
    money=copy.deepcopy(base);money['rascunhos']=[{'id':'money-intent','tipo':'plano','campos':{'titulo':'Quero guardar R$ 1500,50 para GOAL_CANARY'},'acao':'criar','porque':'Pedido explícito sintético'}]
    mc=a.contexto(b,money['rascunhos'],hoje)
    mv=next(v['ref'] for v in mc['publico']['valores_disponiveis'] if v['campo']=='valor_centavos')
    add('valor já declarado preenche meta financeira sem perguntar de novo','triagem.agente_aplicar',{**money,'resposta':{'registros':[{'ref':'rascunho_0','tipo':'plano_financeiro','campos':[{'campo':'meta_centavos','valor':mv}]}],'relacoes':[],'pergunta':None}})
    future=copy.deepcopy(base);future['rascunhos'][1]['campos']['titulo']='Quero chegar em 100% do BOOK_CANARY'
    add('intenção de progresso não é uma observação','triagem.agente_contexto',future)
    quoted_money=copy.deepcopy(base);quoted_money['rascunhos'][0]['campos']['titulo']='Quero comprar “GOAL_CANARY”'
    add('título entre aspas não inventa uma ação de leitura em outro domínio','triagem.agente_contexto',quoted_money)
    invalid=[]
    def bad(name,r):invalid.append({'nome':name,'operacao':'triagem.agente_aplicar','entrada':{**base,'resposta':r}})
    for name,record in [('referência inventada',{'ref':'rascunho_1','tipo':'livro','campos':[{'campo':'titulo','valor':'texto_privado_inventado'}]}),
                        ('minutos não viram porcentagem',{'ref':'rascunho_1','tipo':'livro','campos':[{'campo':'progresso_bp','valor':v('dias_semana')}]}),
                        ('não inventa motivos',{'ref':'rascunho_0','tipo':'plano','campos':[{'campo':'porque','valor':v('titulo')}]}),
                        ('origem privada não pode ser alvo',{'ref':'novo_0','tipo':'compromisso','campos':[{'campo':'origem_real','valor':v('titulo')}]}),
                        ('valor literal recusado',{'ref':'rascunho_1','tipo':'livro','campos':[{'campo':'dias_semana','valor':3}]})]:
        bad(name,{'registros':[record],'relacoes':[],'pergunta':None})
    bad('observação não migra para outro rascunho',{'registros':[{'ref':'rascunho_0','tipo':'livro','campos':[{'campo':'progresso_bp','valor':v('progresso_bp')}]}],'relacoes':[],'pergunta':None})
    bad('pergunta não pode inventar referência privada',{'registros':[],'relacoes':[],'pergunta':{'ref':'rascunho_1','campo':'dias_semana','texto':'Como vai {{id_inventado}}?'}})
    bad('pergunta sem necessidade',{'registros':[],'relacoes':[],'pergunta':{'ref':'rascunho_0','campo':'titulo'}})
    bad('vínculo com alias inventado',{'registros':[],'relacoes':[{'de':'inventado','para':'rascunho_0','tipo':'apoia'}],'pergunta':None})
    for c in invalid:
        if isinstance(c['entrada']['resposta'].get('pergunta'),dict):c['entrada']['resposta']['pergunta'].setdefault('texto','Qual área faz sentido para {{rascunho_0}}?')
        try:t.executar(c['operacao'],c['entrada'])
        except Exception:pass
        else:raise AssertionError(c['nome'])
    return {'gerado_por':'fintips.triagem_agente (fontes sintéticas)','casos':cases,'recusados':invalid}
