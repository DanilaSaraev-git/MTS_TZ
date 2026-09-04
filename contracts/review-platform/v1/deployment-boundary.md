# Deployment boundary v1

HTTP v1 предназначен для одного доверенного deployment. Operator заранее настраивает ровно одного actor, одну organization и один workspace. `GET /v1/bootstrap` возвращает этот actor, workspace и публичные лимиты.

`Actor` — идентичность только для атрибуции созданных документов, запусков, реплик и решений человека. Контракт не устанавливает личность caller и не содержит механизма управления доступом. Любой caller, достигший HTTP API, действует как настроенный actor; поэтому v1 нельзя напрямую публиковать в недоверенную сеть.

`workspaceId` в URL — namespace, а не доказательство доступа. Backend принимает только ID настроенного workspace. Другой ID считается обычным несовпадением namespace и возвращает `404` без отдельной access-control семантики.

`organization_id` хранится в `Workspace` и доменных записях как namespace и future seam для возможной SaaS-эволюции. В v1 это не security boundary и не означает одновременную работу с несколькими организациями.

Защита процесса и сети, через которую operator открывает deployment, находится за пределами этого продуктового контракта. Server-side credentials провайдера LLM также отдельны от HTTP caller; ошибка Model Adapter `authentication_failed` относится только к провайдеру модели.
