python manage.py makemigrations --no-input
python manage.py migrate --no-input
python manage.py seed_admin
python manage.py runserver 0.0.0.0:8000