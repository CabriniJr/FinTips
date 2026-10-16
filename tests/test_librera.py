import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ouro_librera import gerar


def test_automatic_source_preserves_manual_corrections_identity_and_history():
    cases={c['nome']:c['resultado'] for c in gerar()['casos']}
    first=cases['primeira_importacao']['leitura']
    assert cases['repeticao']['leitura']==first
    assert cases['atualizacao_mesmo_dia']['leitura']['livros'][0]['observacoes'][0]['progresso_bp']==3200
    assert cases['arquivo_atrasado']['leitura']==first
    assert cases['correcao_usuario_vence']['leitura']['livros'][0]['observacoes'][0]['progresso_bp']==3600
    assert len(cases['novo_dia']['leitura']['livros'][0]['observacoes'])==2
    assert len(cases['outro_perfil']['leitura']['livros'])==2
    assert cases['futuro']['leitura']['livros']==[]
    assert cases['removido_nao_reaparece']['leitura']['livros']==[]
    assert 'CANARY' not in str(first)
