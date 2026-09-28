# Waivers

Exceções aprovadas a políticas. Cada arquivo `WVR-AAAA-NNN.yaml` segue
[schema/waiver.schema.json](schema/waiver.schema.json); veja o exemplo comentado em
[templates/waiver-example.yaml](../templates/waiver-example.yaml).

- Pedido de exceção = PR neste repositório. O CODEOWNER de AppSec aprova o PR e assina
  como `approved_by` (diferente de `requested_by`).
- Validade máxima de 90 dias. Waiver expirado é ignorado e o achado volta a bloquear;
  o CI deste repositório falha enquanto houver waiver expirado, forçando a limpeza.
- O waiver aparece no relatório do PR, no SARIF (como supressão) e no `result.json`
  atestado, com o id.

Não existe override por comentário no PR (`/governance-bypass`): comentário é editável,
não separa autor de aprovador e não se amarra ao commit (ADR-GOV-000).
