# Calibração continua no lab ../vendas (5 envios/dia + scorecard).
# Playbooks aprovados migram para defaults do Flow Studio neste repo
# (agent_config_versions kind=outbound|inbound|playbook).
#
# Fluxo amarrado no produto:
# Contato → enqueue (Hermes + config publicada) → fila → process_due/Evolution
# → lead stage sent → inbound webhook (só prospect) → KB/persona → reply/dispatch
