"""Padrões pré-prontos (packs de serviço), sem canvas.

Cada pack = nicho + oferta + FAQs do pack + ângulos extras + ritmo sugerido.
Critério mínimo: pains≥5, ctas≥3, faqs≥5 (openings em openings.py ≥3).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FaqSeed:
    question: str
    answer: str


@dataclass(frozen=True)
class ServicePack:
    key: str
    label: str
    blurb: str
    offer: str
    pains: tuple[str, ...]
    ctas: tuple[str, ...]
    daily_sends: int
    faqs: tuple[FaqSeed, ...]
    detect: tuple[str, ...]  # substrings para detect_niche
    # Janela comercial sugerida (horas locais) e cadência de follow-up
    quiet_start: int = 9
    quiet_end: int = 18
    fu_n1_hours: int = 24
    fu_n3_hours: int = 72
    fu_objection_hours: int = 72


SERVICE_PACKS: dict[str, ServicePack] = {
    "clinica": ServicePack(
        key="clinica",
        label="Clínica / saúde",
        blurb="Menos faltas, confirmação e triagem no WhatsApp",
        offer="lembrete e confirmação de consulta + triagem no WhatsApp",
        pains=(
            "paciente marca e falta no dia, agenda fica buraco",
            "secretária perde tempo confirmando consulta uma a uma no WhatsApp",
            "WhatsApp da clínica vira fila sem triagem nem lembrete",
            "paciente pergunta o mesmo (endereço, convênio) o dia todo",
            "retorno e exame ficam sem confirmação e a sala sobra vazia",
            "plantão de feriado vira bagunça de mensagens sem prioridade",
        ),
        ctas=(
            "Hoje vocês confirmam consulta manual ou no automático?",
            "Quantas faltas vocês têm por semana?",
            "A triagem do WhatsApp está com alguém dedicado?",
            "Vocês retomam quem pediu horário e não fechou?",
        ),
        daily_sends=10,
        quiet_start=8,
        quiet_end=18,
        fu_n1_hours=24,
        fu_n3_hours=72,
        faqs=(
            FaqSeed(
                "Vocês atendem convênio?",
                "Atendemos particular e alguns convênios. Me diga o seu que confirmo e já te passo a próxima vaga.",
            ),
            FaqSeed(
                "Qual o horário?",
                "Temos horários nesta semana. Prefere manhã ou tarde?",
            ),
            FaqSeed(
                "Onde fica?",
                "Te mando o endereço e o Maps. Quer que eu já reserve um horário?",
            ),
            FaqSeed(
                "Como confirma a consulta?",
                "Mandamos lembrete no WhatsApp e pedimos um ok. Quer ver como fica na prática?",
            ),
            FaqSeed(
                "Tem encaixe essa semana?",
                "Depende da especialidade. Me diga o que precisa que checo as próximas vagas.",
            ),
            FaqSeed(
                "Primeira consulta demora quanto?",
                "Varia um pouco. Prefere que um humano te passe a faixa e as opções de horário?",
            ),
        ),
        detect=(
            "clínica",
            "clinica",
            "odont",
            "dent",
            "médic",
            "medic",
            "fisioter",
            "consultório",
            "consultorio",
            "psicolog",
            "nutri",
        ),
    ),
    "loja": ServicePack(
        key="loja",
        label="Loja / varejo",
        blurb="Catálogo e venda além do Instagram",
        offer="catálogo e checkout próprio, com retomada no WhatsApp",
        pains=(
            "venda presa no Instagram, sem catálogo ou checkout próprio",
            "cliente pergunta preço e estoque no WhatsApp o dia todo",
            "difícil vender fora do horário sem loja online",
            "carrinho abandona e ninguém retoma no WhatsApp",
            "troca e prazo de entrega viram fila repetida no zap",
            "promoção no story e o link some, lead esfria",
        ),
        ctas=(
            "Hoje vendem mais pelo Instagram ou já têm site que converte?",
            "O gargalo é catálogo ou checkout?",
            "Quanto tempo por dia vai em pergunta de preço no WhatsApp?",
            "Vocês retomam quem perguntou preço e sumiu?",
        ),
        daily_sends=12,
        faqs=(
            FaqSeed(
                "Tem frete?",
                "Sim, calculamos pelo CEP. Me passa o seu que te digo as opções.",
            ),
            FaqSeed(
                "Aceita Pix?",
                "Aceitamos Pix e cartão. Posso te mandar o link de pagamento agora.",
            ),
            FaqSeed(
                "Tem troca?",
                "Sim, política clara. Quer que eu te resuma em uma frase?",
            ),
            FaqSeed(
                "Tem esse modelo em estoque?",
                "Me diga o modelo ou manda uma foto que eu confirmo disponibilidade.",
            ),
            FaqSeed(
                "Qual o prazo de entrega?",
                "Depende da região. Me passa o CEP que te passo a previsão.",
            ),
            FaqSeed(
                "Tem desconto no Pix?",
                "Em alguns itens sim. Quer que eu te mostre as opções de hoje?",
            ),
        ),
        detect=(
            "loja",
            "moda",
            "roupa",
            "móvel",
            "movel",
            "ótica",
            "otica",
            "floricultura",
            "varejo",
            "calçado",
            "calcado",
            "boutique",
            "armarinho",
        ),
    ),
    "food": ServicePack(
        key="food",
        label="Restaurante / food",
        blurb="Cardápio digital e pedido sem bagunça",
        offer="cardápio digital e pedido online sem depender só de app",
        pains=(
            "pedidos 100% no WhatsApp, bagunça no horário de pico",
            "cardápio muda e o cliente ainda vê preço velho",
            "dependência de app de delivery com taxa alta",
            "erro de pedido por mensagem solta no grupo",
            "mesa e delivery misturados no mesmo zap",
            "promoção do dia some e o cliente pede item que acabou",
        ),
        ctas=(
            "Pedidos ainda 100% no WhatsApp ou já têm cardápio digital?",
            "A taxa do app está comendo a margem?",
            "No pico, quem organiza o pedido: cozinha ou o zap?",
            "Vocês retomam quem pediu cardápio e não fechou?",
        ),
        daily_sends=12,
        quiet_start=10,
        quiet_end=22,
        fu_n1_hours=12,
        fu_n3_hours=48,
        fu_objection_hours=48,
        faqs=(
            FaqSeed(
                "Faz entrega?",
                "Sim na região. Me diga o bairro que confirmo tempo e taxa.",
            ),
            FaqSeed(
                "Tem cardápio?",
                "Te mando o cardápio atualizado com preços de hoje. Quer link agora?",
            ),
            FaqSeed(
                "Aceita reserva?",
                "Para salão sim. Me diga data, horário e quantas pessoas.",
            ),
            FaqSeed(
                "Qual o tempo de entrega?",
                "Varia com o bairro e o movimento. Me passa o CEP que te dou a faixa.",
            ),
            FaqSeed(
                "Tem taxa de entrega?",
                "Sim, por região. Me diga o bairro que confirmo o valor.",
            ),
            FaqSeed(
                "Aceita Pix?",
                "Sim. Posso te mandar o pedido montado com o total e a chave.",
            ),
        ),
        detect=(
            "restaurante",
            "pizzaria",
            "hamburguer",
            "lanchonete",
            "lanch",
            "bar ",
            "café",
            "cafe",
            "food",
            "padaria",
            "confeit",
            "marmita",
            "açai",
            "acai",
        ),
    ),
    "salao": ServicePack(
        key="salao",
        label="Salão / barbearia",
        blurb="Agenda, confirmação e menos furo no horário",
        offer="agenda e confirmação de horário no WhatsApp",
        pains=(
            "cliente marca e não aparece, horário fica buraco",
            "WhatsApp vira fila de 'tem horário amanhã?'",
            "confirmação ainda é uma a uma no zap",
            "promoção no Instagram e ninguém agenda de verdade",
            "equipe perde tempo repetindo preço de corte e escova",
            "encaixe de última hora bagunça a agenda do dia",
        ),
        ctas=(
            "Vocês confirmam horário no dia anterior?",
            "Quantos furos de agenda por semana?",
            "O zap ainda é 100% manual pra marcar horário?",
            "O gargalo é agenda ou resposta de preço?",
        ),
        daily_sends=10,
        quiet_start=9,
        quiet_end=20,
        fu_n1_hours=24,
        fu_n3_hours=72,
        faqs=(
            FaqSeed(
                "Tem horário amanhã?",
                "Me diga o serviço e o período (manhã/tarde) que confirmo a próxima vaga.",
            ),
            FaqSeed(
                "Quanto custa o corte?",
                "Depende do serviço. Me diga o que precisa que te passo a faixa.",
            ),
            FaqSeed(
                "Aceita Pix?",
                "Sim. Depois de marcar te mando o valor e a forma de pagamento.",
            ),
            FaqSeed(
                "Atende criança?",
                "Em vários casos sim. Me diga a idade e o serviço que confirmo.",
            ),
            FaqSeed(
                "Precisa agendar?",
                "Sim, pra garantir horário. Prefere manhã ou tarde?",
            ),
        ),
        detect=("salão", "salao", "barbearia", "barbeiro", "cabeleireir", "manicure", "nail"),
    ),
    "estetica": ServicePack(
        key="estetica",
        label="Estética / beleza",
        blurb="Triagem de procedimento e agenda sem bagunça",
        offer="triagem de interesse + agendamento de avaliação no WhatsApp",
        pains=(
            "lead pergunta preço de procedimento e some",
            "WhatsApp mistura curiosidade com cliente pronto pra agendar",
            "avaliação marcada sem contexto do que a pessoa quer",
            "mesmas dúvidas de pós e contraindicação o dia todo",
            "promoção no story e a agenda não enche",
        ),
        ctas=(
            "A triagem de procedimento ainda é 100% humana no zap?",
            "Vocês retomam quem pediu preço e não agendou?",
            "O gargalo é avaliação ou resposta de orçamento?",
        ),
        daily_sends=10,
        quiet_start=9,
        quiet_end=19,
        fu_n1_hours=24,
        fu_n3_hours=72,
        faqs=(
            FaqSeed(
                "Quanto custa?",
                "Depende do procedimento. Me diga o que busca que te passo uma faixa e a próxima avaliação.",
            ),
            FaqSeed(
                "Precisa de avaliação?",
                "Na maioria dos casos sim. Prefere manhã ou tarde esta semana?",
            ),
            FaqSeed(
                "Dói?",
                "Varia com o procedimento. Quer que um humano te explique com calma?",
            ),
            FaqSeed(
                "Tem contraindicação?",
                "Depende do histórico. Me diga o procedimento que te oriento o próximo passo.",
            ),
            FaqSeed(
                "Aceita Pix?",
                "Sim. Depois da avaliação alinhamos valor e pagamento.",
            ),
        ),
        detect=("estética", "estetica", "spa ", "depilação", "depilacao", "harmonização", "harmonizacao", "limpeza de pele"),
    ),
    "oficina": ServicePack(
        key="oficina",
        label="Oficina / auto",
        blurb="Orçamento e status do serviço sem fila no zap",
        offer="orçamento e atualização de status no WhatsApp",
        pains=(
            "cliente pergunta status do carro o dia todo",
            "orçamento repetido pra todo mundo que manda foto",
            "aprovação demora e a oficina fica parada",
            "WhatsApp mistura emergência, peça e 'quanto fica?'",
            "ninguém retoma quem pediu orçamento e sumiu",
        ),
        ctas=(
            "Status do serviço ainda é 100% manual no zap?",
            "Quantos orçamentos ficam sem retorno por semana?",
            "O gargalo é orçamento ou aprovação do cliente?",
        ),
        daily_sends=10,
        quiet_start=8,
        quiet_end=18,
        fu_n1_hours=24,
        fu_n3_hours=72,
        faqs=(
            FaqSeed(
                "Quanto fica?",
                "Depende do serviço. Me manda o modelo e o que precisa que te passo uma faixa.",
            ),
            FaqSeed(
                "Quanto tempo demora?",
                "Varia com a peça e a fila. Me diga o serviço que te dou a previsão.",
            ),
            FaqSeed(
                "Tem horário hoje?",
                "Me diga o período e o que precisa que confirmo a encaixe.",
            ),
            FaqSeed(
                "Aceita Pix?",
                "Sim. Depois de aprovar o orçamento te mando o valor.",
            ),
            FaqSeed(
                "Faz diagnóstico?",
                "Sim. Prefere deixar o carro de manhã ou à tarde?",
            ),
        ),
        detect=("oficina", "mecânic", "mecanic", "auto center", "autocenter", "funilaria", "borracharia"),
    ),
    "servico": ServicePack(
        key="servico",
        label="Serviço local",
        blurb="Agenda e WhatsApp organizados",
        offer="agenda/reserva e WhatsApp mais organizado para orçamento",
        pains=(
            "agenda manual e WhatsApp vira fila de orçamento",
            "cliente marca e some sem confirmação",
            "difícil organizar horários sem reserva online",
            "orçamento repetido pra todo mundo que pergunta",
            "no-show em horário reservado come a tarde",
            "lead pede preço e ninguém retoma no dia seguinte",
        ),
        ctas=(
            "Agenda hoje é manual ou já têm reserva online?",
            "Quantos orçamentos vocês mandam por dia no zap?",
            "Vocês confirmam horário no dia anterior?",
            "O gargalo é agenda ou resposta de orçamento?",
        ),
        daily_sends=10,
        quiet_start=9,
        quiet_end=18,
        faqs=(
            FaqSeed(
                "Quanto custa?",
                "Depende do serviço. Me diga o que precisa que te passo uma faixa sem compromisso.",
            ),
            FaqSeed(
                "Tem horário amanhã?",
                "Me diga o período (manhã/tarde) que confirmo a próxima vaga.",
            ),
            FaqSeed(
                "Atende minha região?",
                "Na maioria dos bairros sim. Me fala a cidade ou o bairro.",
            ),
            FaqSeed(
                "Demora quanto?",
                "Varia com o serviço. Me descreve em uma frase que te digo a faixa de tempo.",
            ),
            FaqSeed(
                "Precisa agendar?",
                "Sim, pra garantir horário. Prefere manhã ou tarde?",
            ),
            FaqSeed(
                "Aceita Pix?",
                "Sim. Depois de alinhar o serviço te mando o valor e a forma de pagamento.",
            ),
        ),
        detect=("academia", "pilates", "serviço", "servico", "lavagem", "personal", "jardinagem"),
    ),
    "imobiliaria": ServicePack(
        key="imobiliaria",
        label="Imobiliária",
        blurb="Qualificação de leads e visitas sem caos no zap",
        offer="triagem de interesse + agendamento de visita no WhatsApp",
        pains=(
            "lead quente some no meio de 50 conversas abertas",
            "visita marcada e o cliente não confirma",
            "mesmo anúncio gera as mesmas 10 perguntas o dia todo",
            "corretor perde tempo com lead fora do perfil",
            "follow-up de visita esfria e ninguém retoma",
        ),
        ctas=(
            "Hoje a triagem de leads é manual no WhatsApp?",
            "Quantas visitas ficam sem confirmação por semana?",
            "Vocês filtram orçamento e região antes da visita?",
        ),
        daily_sends=12,
        quiet_start=9,
        quiet_end=19,
        fu_n1_hours=24,
        fu_n3_hours=96,
        faqs=(
            FaqSeed(
                "Aceita FGTS?",
                "Depende do imóvel e do banco. Me diga o código do anúncio que verifico.",
            ),
            FaqSeed(
                "Posso visitar?",
                "Sim. Me diga o dia e o período preferidos que confirmo com o corretor.",
            ),
            FaqSeed(
                "Está disponível?",
                "Vou checar o status atual e já te retorno. Qual o código do anúncio?",
            ),
            FaqSeed(
                "Qual a faixa de preço?",
                "Me diga região e tipo (apto/casa) que te passo as opções nessa faixa.",
            ),
            FaqSeed(
                "Aceita financiamento?",
                "Na maioria dos casos sim. Prefere que um corretor te explique as condições?",
            ),
        ),
        detect=("imóbil", "imobil", "corretor", "imóveis", "imoveis", "apartamento", "condo"),
    ),
    "educacao": ServicePack(
        key="educacao",
        label="Educação / curso",
        blurb="Matrícula e dúvidas repetidas no automático",
        offer="FAQ de curso + captura de interesse e agendamento de conversa",
        pains=(
            "secretaria responde as mesmas dúvidas de matrícula",
            "lead pede valor e some sem follow-up",
            "turmas abertas e ninguém retoma interessados",
            "documento e horário viram fila no zap",
            "prova ou vestibular geram pico de mensagem sem triagem",
        ),
        ctas=(
            "As dúvidas de matrícula ainda são 100% manuais?",
            "Vocês retomam quem pediu preço e não fechou?",
            "O pico de mensagem é matrícula ou turma nova?",
        ),
        daily_sends=12,
        faqs=(
            FaqSeed(
                "Qual o valor?",
                "Temos planos. Me diga o curso ou a turma que te passo a faixa e condições.",
            ),
            FaqSeed(
                "Tem vaga?",
                "Sim nesta turma. Posso te reservar uma pré-vaga enquanto alinhamos?",
            ),
            FaqSeed(
                "É presencial?",
                "Temos modalidades. Me diga sua cidade que confirmo.",
            ),
            FaqSeed(
                "Quando começa?",
                "Me diga o curso que te passo a próxima turma e o link de interesse.",
            ),
            FaqSeed(
                "Tem material incluso?",
                "Depende do curso. Quer que eu te resuma o que entra no pacote?",
            ),
        ),
        detect=("escola", "curso", "faculdade", "colégio", "colegio", "idioma", "educa", "treinamento"),
    ),
    "advocacia": ServicePack(
        key="advocacia",
        label="Advocacia",
        blurb="Triagem ética e agendamento de consulta",
        offer="triagem inicial no WhatsApp + agenda de consulta com o escritório",
        pains=(
            "WhatsApp mistura cliente urgente com curiosidade",
            "consulta marcada sem contexto do caso",
            "equipe perde tempo em perguntas fora do escopo",
            "prazo apertado chega tarde na fila do zap",
            "retorno de consulta some sem confirmação",
        ),
        ctas=(
            "A triagem inicial ainda é 100% humana no zap?",
            "Vocês perdem tempo com casos fora da área?",
            "Urgência de prazo chega organizada ou misturada?",
        ),
        daily_sends=10,
        quiet_start=9,
        quiet_end=18,
        fu_n1_hours=48,
        fu_n3_hours=96,
        fu_objection_hours=96,
        faqs=(
            FaqSeed(
                "Atendem minha área?",
                "Me diga o tema em uma frase (trabalhista, família, etc.) que confirmo.",
            ),
            FaqSeed(
                "Quanto custa a consulta?",
                "A consulta tem valor combinado. Prefere que um humano te confirme e agenda?",
            ),
            FaqSeed(
                "É urgente?",
                "Se for prazo, diga a data limite que priorizamos o retorno humano.",
            ),
            FaqSeed(
                "Posso mandar documento?",
                "Sim, em PDF ou foto legível. Depois um humano te confirma o próximo passo.",
            ),
            FaqSeed(
                "Atendem online?",
                "Em vários casos sim. Me diga a cidade e o tema que alinhamos o formato.",
            ),
        ),
        detect=("advoc", "jurídic", "juridic", "escritório de advoc", "oab"),
    ),
    "pet": ServicePack(
        key="pet",
        label="Pet / clínica vet",
        blurb="Lembretes de consulta e dúvidas repetidas",
        offer="lembrete de consulta/vacina + FAQ no WhatsApp",
        pains=(
            "tutor esquece retorno e vacina",
            "WhatsApp cheio de 'vocês abrem sábado?'",
            "agenda do banho/tosa sem confirmação",
            "emergência e dúvida leve misturam na mesma fila",
            "promoção de vacina e ninguém confirma horário",
        ),
        ctas=(
            "Lembretes de vacina/consulta ainda são manuais?",
            "O zap da clínica está virando fila o dia todo?",
            "Banho e tosa confirmam no dia anterior?",
        ),
        daily_sends=10,
        faqs=(
            FaqSeed(
                "Abre sábado?",
                "Sim em horário reduzido. Te passo as opções desta semana?",
            ),
            FaqSeed(
                "Tem banho e tosa?",
                "Sim. Me diga porte e data preferida que confirmo a vaga.",
            ),
            FaqSeed(
                "Aceita convênio pet?",
                "Alguns planos sim. Me diga o nome do plano.",
            ),
            FaqSeed(
                "Precisa vacina?",
                "Depende do histórico. Me diga a espécie e a idade que te oriento o próximo passo.",
            ),
            FaqSeed(
                "É emergência?",
                "Se for urgência, diga o sintoma em uma frase que priorizamos o retorno.",
            ),
        ),
        detect=("pet", "vet", "veterin", "banho e tosa", "petshop"),
    ),
    "geral": ServicePack(
        key="geral",
        label="Negócio local",
        blurb="WhatsApp organizado e resposta no ritmo certo",
        offer="organizar o WhatsApp, triar dúvida repetida e retomar quem esfriou",
        pains=(
            "atendimento repetitivo no WhatsApp come o dia",
            "lead some no Instagram sem follow-up",
            "processos manuais atrasam resposta ao cliente",
            "equipe mistura venda, dúvida e reclamação no mesmo chat",
            "ninguém sabe quem já foi respondido ontem",
        ),
        ctas=(
            "O maior gargalo hoje é atendimento, agenda ou vendas no zap?",
            "Vocês retomam quem perguntou e não fechou?",
            "Vale alinhar um ritmo diário de resposta essa semana?",
        ),
        daily_sends=10,
        faqs=(
            FaqSeed(
                "Como funciona?",
                "A gente organiza o WhatsApp com respostas prontas do seu nicho e fila do dia. Quer ver um exemplo?",
            ),
            FaqSeed(
                "Preciso mudar meu número?",
                "Não. Você usa o número que já tem. Quer que eu te explique o próximo passo?",
            ),
            FaqSeed(
                "Quanto tempo por dia?",
                "Você define o ritmo (ex.: 5 a 15 contatos/dia). Prefere começar baixo?",
            ),
            FaqSeed(
                "E se a pessoa pedir humano?",
                "O bot escala e você assume. Quer que eu te mostre como fica na prática?",
            ),
            FaqSeed(
                "Serve pro meu tipo de negócio?",
                "Se o WhatsApp é canal de venda ou agenda, sim. Me diga o nicho em uma palavra.",
            ),
        ),
        detect=(),
    ),
}


def list_packs() -> list[ServicePack]:
    # geral por último
    keys = [k for k in SERVICE_PACKS if k != "geral"] + ["geral"]
    return [SERVICE_PACKS[k] for k in keys]


def get_pack(key: str | None) -> ServicePack:
    if key and key in SERVICE_PACKS:
        return SERVICE_PACKS[key]
    return SERVICE_PACKS["geral"]


# Ordem: específico antes de genérico (salao/estetica/oficina antes de servico)
_DETECT_ORDER = (
    "pet",
    "advocacia",
    "imobiliaria",
    "educacao",
    "estetica",
    "salao",
    "oficina",
    "clinica",
    "food",
    "servico",
    "loja",
)


def detect_pack_key(company: str | None, name: str | None) -> str:
    blob = f"{company or ''} {name or ''}".lower()
    for key in _DETECT_ORDER:
        pack = SERVICE_PACKS[key]
        for token in pack.detect:
            if token.lower() in blob:
                return key
    return "geral"
