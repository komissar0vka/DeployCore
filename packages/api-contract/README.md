# Контракт DeployCore

`openapi.json` — снимок схемы FastAPI. После изменения API обновите файл из `apps/server` в активном виртуальном окружении:

```bash
python -c 'import json; from deploycore.main import app; print(json.dumps(app.openapi(), indent=2))' > ../../packages/api-contract/openapi.json
```

Smoke-тест сравнивает снимок с ответом запущенного сервера.
