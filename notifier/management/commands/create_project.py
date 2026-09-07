from django.core.management.base import BaseCommand

from notifier.models import Project, generate_token, hash_token


class Command(BaseCommand):
    help = "Создать проект и вывести токен (показывается один раз)"

    def add_arguments(self, parser):
        parser.add_argument("name", type=str, help="Название проекта")
        parser.add_argument("--slug", type=str, help="Slug (по умолчанию из name)")
        parser.add_argument("--site-url", type=str, default="")

    def handle(self, *args, **options):
        name = options["name"]
        slug = options.get("slug") or name.lower().replace(" ", "-")

        if Project.objects.filter(slug=slug).exists():
            self.stderr.write(f"Проект со slug '{slug}' уже существует")
            return

        token = generate_token()
        project = Project.objects.create(
            name=name,
            slug=slug,
            site_url=options["site_url"],
            token_hash=hash_token(token),
        )

        self.stdout.write(self.style.SUCCESS(f"Проект '{project.name}' создан"))
        self.stdout.write(f"  slug:  {project.slug}")
        self.stdout.write(self.style.WARNING(f"  ТОКЕН: {token}"))
        self.stdout.write("  ⚠️  Сохраните токен — повторно его получить нельзя!")
