Linux Ubuntu

1. Установите Docker Engine с плагином Docker Compose по инструкции https://docs.docker.com/engine/install/ubuntu/

2. Откройте папку проекта в приложении Файлы, нажмите правой кнопкой мыши на свободном месте и выберите Открыть в терминале

3. Поместите ваш файл с документами в папку data под именем posts.csv, файл должен быть в кодировке UTF-8 с колонками text, created_date, rubrics. Формат даты: YYYY-MM-DD HH:MM:SS, формат рубрик: список строк, например ['news', 'science']

4. Введите команды:

if [ ! -e .env ]; then cp .env.example .env; fi

nano .env

Заполните POSTGRES_DB именем базы, POSTGRES_USER именем пользователя, POSTGRES_PASSWORD вашим паролем. Остальные значения оставьте без изменений, нажмите Ctrl+O и Enter для сохранения файла, затем Ctrl+X для выхода из редактора

sudo systemctl start docker

echo vm.max_map_count=1048576 | sudo tee /etc/sysctl.d/99-document-search.conf

sudo sysctl -p /etc/sysctl.d/99-document-search.conf

sudo docker compose config --quiet

sudo docker compose up -d --build --wait

sudo docker compose exec -T app python setup_data.py

5. Откройте в браузере http://127.0.0.1:8000/docs



Windows

1. Установите и запустите Docker Desktop

2. Откройте папку проекта в Проводнике, в адресной строке введите powershell и нажмите Enter

3. Поместите ваш файл с документами в папку data под именем posts.csv, файл должен быть в кодировке UTF-8 с колонками text, created_date, rubrics. Формат даты: YYYY-MM-DD HH:MM:SS, формат рубрик: список строк, например ['news', 'science']

4. Введите команды:

if (-not (Test-Path .env)) { Copy-Item .env.example .env }

notepad .env

Заполните POSTGRES_DB именем базы, POSTGRES_USER именем пользователя, POSTGRES_PASSWORD вашим паролем. Остальные значения оставьте без изменений, сохраните файл и закройте Блокнот

docker compose config --quiet

docker compose up -d --build --wait

docker compose exec -T app python setup_data.py

5. Откройте в браузере http://127.0.0.1:8000/docs
