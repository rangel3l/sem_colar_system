import random

def embaralhar_questoes(questoes):
    return random.sample(questoes, len(questoes))

def embaralhar_alternativas(questao):
    enunciado, alternativas = questao
    alternativas_emb = random.sample(alternativas, len(alternativas))
    return enunciado, alternativas_emb

def embaralhar_tudo(questoes):
    novas = []
    for q in questoes:
        novas.append(embaralhar_alternativas(q))
    return embaralhar_questoes(novas)
