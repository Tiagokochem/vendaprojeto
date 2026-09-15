"""Padrões pré-prontos (packs de serviço), sem canvas.

Cada pack = nicho + oferta + FAQs do pack + ângulos extras + ritmo sugerido.
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
        ),
        ctas=(
            "Hoje vocês confirmam consulta manual ou no automático?",
            "Quantas faltas vocês têm por semana?",
            "A triagem do WhatsApp está com alguém dedicado?",
        ),
        daily_sends=10,
        faqs=(
            FaqSeed("Vocês atendem convênio?", "Atendemos particular e alguns convênios, me diga o seu que confirmo."),
            FaqSeed("Qual o horário?", "Funcionamos em horário comercial; posso te passar as opções desta semana."),
            FaqSeed("Onde fica?", "Te mando o endereço e o link do Maps assim que confirmarmos o horário."),
        ),
        detect=("clínica", "clinica", "odont", "dent", "médic", "medic", "estética", "estetica", "fisioter", "consultório", "consultorio"),
    ),
    "loja": ServicePack(
        key="loja",
        label="Loja / varejo",
        blurb="Catálogo e venda além do Instagram",
        offer="site/loja online com catálogo e checkout próprio",
        pains=(
            "venda presa no Instagram, sem catálogo ou checkout próprio",
            "cliente pergunta preço e estoque no WhatsApp o dia todo",
            "difícil vender fora do horário sem loja online",
            "carrinho abandona e ninguém retoma no WhatsApp",
        ),
        ctas=(
            "Hoje vendem mais pelo Instagram ou já têm site que converte?",
            "O gargalo é catálogo ou checkout?",
            "Quanto tempo por dia vai em pergunta de preço no WhatsApp?",
        ),
        daily_sends=12,
        faqs=(
            FaqSeed("Tem frete?", "Sim, calculamos pelo CEP. Me passa o seu que te digo as opções."),
            FaqSeed("Aceita Pix?", "Aceitamos Pix e cartão. Posso te mandar o link de pagamento."),
            FaqSeed("Tem troca?", "Sim, política de troca clara no site, te resumo em uma frase se quiser."),
        ),
        detect=("loja", "moda", "roupa", "móvel", "movel", "ótica", "otica", "floricultura", "varejo", "calçado", "calcado"),
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
        ),
        ctas=(
            "Pedidos ainda 100% no WhatsApp ou já têm cardápio digital?",
            "A taxa do app está comendo a margem?",
        ),
        daily_sends=15,
        faqs=(
            FaqSeed("Faz entrega?", "Sim, na região, me diga o bairro que confirmo tempo e taxa."),
            FaqSeed("Tem cardápio?", "Te mando o cardápio atualizado com preços de hoje."),
            FaqSeed("Aceita reserva?", "Para salão sim, me diga data, horário e quantas pessoas."),
        ),
        detect=("restaurante", "pizzaria", "hamburguer", "lanchonete", "lanch", "bar ", "café", "cafe", "food", "padaria", "confeit"),
    ),
    "servico": ServicePack(
        key="servico",
        label="Serviço local",
        blurb="Agenda e WhatsApp organizados",
        offer="site com agenda/reserva e WhatsApp mais organizado",
        pains=(
            "agenda manual e WhatsApp vira fila de orçamento",
            "cliente marca e some sem confirmação",
            "difícil organizar horários sem reserva online",
            "orçamento repetido pra todo mundo que pergunta",
        ),
        ctas=(
            "Agenda hoje é manual ou já têm reserva online?",
            "Quantos orçamentos vocês mandam por dia no zap?",
        ),
        daily_sends=10,
        faqs=(
            FaqSeed("Quanto custa?", "Depende do serviço, me diga o que precisa que te passo uma faixa sem compromisso."),
            FaqSeed("Tem horário amanhã?", "Me diga o período (manhã/tarde) que confirmo a próxima vaga."),
            FaqSeed("Atende minha região?", "Sim na maioria dos bairros, me fala a cidade/bairro."),
        ),
        detect=("salão", "salao", "barbearia", "academia", "pilates", "oficina", "mecânic", "mecanic", "beleza", "serviço", "servico"),
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
        ),
        ctas=(
            "Hoje a triagem de leads é manual no WhatsApp?",
            "Quantas visitas ficam sem confirmação por semana?",
        ),
        daily_sends=15,
        faqs=(
            FaqSeed("Aceita FGTS?", "Depende do imóvel e do banco, me diga o código do anúncio que verifico."),
            FaqSeed("Posso visitar?", "Sim, me diga o dia e período preferidos que confirmo com o corretor."),
            FaqSeed("Está disponível?", "Vou checar o status atual e já te retorno."),
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
        ),
        ctas=(
            "As dúvidas de matrícula ainda são 100% manuais?",
            "Vocês retoma quem pediu preço e não fechou?",
        ),
        daily_sends=12,
        faqs=(
            FaqSeed("Qual o valor?", "Temos planos, me diga o curso/turma que te passo a faixa e condições."),
            FaqSeed("Tem vaga?", "Sim nesta turma, posso te reservar uma pré-vaga enquanto alinhamos."),
            FaqSeed("É presencial?", "Temos modalidades, me diga sua cidade que confirmo."),
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
        ),
        ctas=(
            "A triagem inicial ainda é 100% humana no zap?",
            "Vocês perdem tempo com casos fora da área?",
        ),
        daily_sends=15,
        faqs=(
            FaqSeed("Atendem minha área?", "Me diga o tema em uma frase (trabalhista, família, etc.) que confirmo."),
            FaqSeed("Quanto custa a consulta?", "A consulta tem valor fixo, um humano te confirma e agenda."),
            FaqSeed("É urgente?", "Se for prazo processual, diga a data limite que priorizamos o retorno humano."),
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
        ),
        ctas=(
            "Lembretes de vacina/consulta ainda são manuais?",
            "O zap da clínica está virando fila o dia todo?",
        ),
        daily_sends=10,
        faqs=(
            FaqSeed("Abre sábado?", "Sim em horário reduzido, te passo as opções desta semana."),
            FaqSeed("Tem banho e tosa?", "Sim, me diga porte e data preferida."),
            FaqSeed("Aceita convênio pet?", "Alguns planos sim, me diga o nome do plano."),
        ),
        detect=("pet", "vet", "veterin", "banho e tosa", "petshop"),
    ),
    "geral": ServicePack(
        key="geral",
        label="Negócio local",
        blurb="Site + WhatsApp sem bagunça",
        offer="site profissional + automação do que hoje é manual no WhatsApp",
        pains=(
            "atendimento repetitivo no WhatsApp come o dia",
            "site fraco ou inexistente, lead some no Instagram",
            "processos manuais atrasam resposta ao cliente",
        ),
        ctas=(
            "Isso encaixa no que vocês precisam agora?",
            "Vale trocar uma ideia rápida essa semana?",
        ),
        daily_sends=15,
        faqs=(
            FaqSeed("Como funciona?", "A gente configura o bot no seu WhatsApp com o seu jeito de atender, sem montar fluxo."),
            FaqSeed("Preciso de site?", "Ajuda, mas o foco é organizar o WhatsApp e a fila de leads."),
            FaqSeed("Quanto custa?", "Temos plano Free pra testar e Pro com mais envios, te explico no trial."),
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


# Ordem importa: mais específico antes de genérico (pet > loja; advocacia > geral)
_DETECT_ORDER = (
    "pet",
    "advocacia",
    "imobiliaria",
    "educacao",
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
