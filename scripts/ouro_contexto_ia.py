from fintips.ai_context import AREAS, READING_STATES, project_context


def ouro_contexto_ia():
    cases = []
    for scopes in ([], ["rotina"], ["planos"], ["leitura"], ["rotina", "planos", "leitura"]):
        for n in range(5):
            fronts = [{"area": area, "total": n, "done": min(i, n)} for i, area in enumerate(AREAS)]
            plans = [{"area": area, "done": i % 2 == 0} for i, area in enumerate(AREAS) for _ in range(n)]
            plans += [{"area": "FOR", "done": False}] if n else []
            reading = [{"state": s, "source": "librera" if i % 2 else "usuario"}
                       for i, s in enumerate(READING_STATES[:n])]
            args = dict(fronts=fronts, plans=plans, reading=reading, scopes=scopes)
            cases.append({"entrada": args, "resultado": project_context(**args)})
    return {"casos": cases}
