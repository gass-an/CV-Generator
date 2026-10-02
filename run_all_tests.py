import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "generator-service"
ADMIN = ROOT / "generator-admin-service"
SHARED = ROOT / "shared"

DB_USER = "cv_generator"
DB_PASSWORD = "cv_generator"
DB_HOST = "127.0.0.1"
DB_PORT = 5433

DATABASES = (
    "cv_generator_test",
    "cv_generator_migration_test",
    "cv_generator_admin_test",
)


def docker(*arguments: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *arguments],
        check=check,
        text=True,
        capture_output=True,
    )


def start_postgres() -> str:
    # Nom unique : on ne réutilise ni n'arrête un conteneur préexistant.
    container_name = f"cv-generator-tests-{uuid.uuid4().hex[:12]}"

    print("\nDémarrage de PostgreSQL 18 pour les tests...", flush=True)

    try:
        docker(
            "run",
            "--detach",
            "--rm",
            "--name",
            container_name,
            "--publish",
            f"{DB_HOST}:{DB_PORT}:5432",
            "--env",
            f"POSTGRES_USER={DB_USER}",
            "--env",
            f"POSTGRES_PASSWORD={DB_PASSWORD}",
            "--env",
            f"POSTGRES_DB={DATABASES[0]}",
            "postgres:18",
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            "Docker est introuvable. Vérifie son installation."
        ) from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            "Impossible de démarrer PostgreSQL.\n"
            "Vérifie que Docker fonctionne et que le port 5433 est libre.\n"
            f"{error.stderr}"
        ) from error

    return container_name


def wait_for_postgres(container_name: str) -> None:
    print("Attente de PostgreSQL...", flush=True)

    deadline = time.monotonic() + 60

    while time.monotonic() < deadline:
        result = docker(
            "exec",
            container_name,
            "pg_isready",
            "-h",
            "127.0.0.1",
            "-U",
            DB_USER,
            "-d",
            DATABASES[0],
            check=False,
        )

        if result.returncode == 0:
            print("PostgreSQL est prêt.", flush=True)
            return

        time.sleep(1)

    raise RuntimeError("PostgreSQL n'est pas devenu disponible après 60 secondes.")


def create_databases(container_name: str) -> None:
    # La première base est déjà créée par l'image officielle PostgreSQL.
    for database_name in DATABASES[1:]:
        print(f"Création de {database_name}...", flush=True)

        docker(
            "exec",
            container_name,
            "createdb",
            "-U",
            DB_USER,
            "-O",
            DB_USER,
            database_name,
        )


def run_step(
    label: str,
    module: str,
    arguments: list[str],
    cwd: Path,
    env: dict[str, str],
) -> None:
    print(f"\n{'=' * 60}", flush=True)
    print(f" {label}", flush=True)
    print(f"{'=' * 60}\n", flush=True)

    subprocess.run(
        [sys.executable, "-m", module, *arguments],
        cwd=cwd,
        env=env,
        check=True,
    )


def main() -> None:
    container_name = start_postgres()

    try:
        wait_for_postgres(container_name)
        create_databases(container_name)

        def database_url(database_name: str) -> str:
            return (
                f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}"
                f"@{DB_HOST}:{DB_PORT}/{database_name}"
            )

        env = os.environ.copy()

        backend_env = {
            **env,
            "DATABASE_URL": database_url(DATABASES[0]),
            "TEST_DATABASE_URL": database_url(DATABASES[0]),
            "MIGRATION_TEST_DATABASE_URL": database_url(DATABASES[1]),
        }

        admin_env = {
            **backend_env,
            "DATABASE_URL": database_url(DATABASES[2]),
            "ADMIN_TEST_DATABASE_URL": database_url(DATABASES[2]),
            "APP_ENV": "test",
            "ADMIN_USERNAME": "administrateur",
            "ADMIN_SESSION_SECRET": "test-only-session-secret-48-characters-long",
            "ADMIN_LOGIN_MAX_ATTEMPTS": "3",
            "ADMIN_BASE_URL": "http://testserver",
            "ADMIN_TIMEZONE": "Pacific/Noumea",
            "ADMIN_COOKIE_SECURE": "false",
            "ADMIN_TRUSTED_PROXY_IPS": "",
        }

        # Laisse la fixture administrateur générer son hash de test.
        admin_env.pop("ADMIN_PASSWORD_HASH", None)

        run_step(
            "Migration de la base backend",
            "alembic",
            ["upgrade", "head"],
            BACKEND,
            backend_env,
        )

        run_step(
            "Migration de la base administration",
            "alembic",
            ["upgrade", "head"],
            BACKEND,
            admin_env,
        )

        run_step(
            "1/3 - Tests shared",
            "pytest",
            ["tests", "-q"],
            SHARED,
            backend_env,
        )

        run_step(
            "2/3 - Tests backend et worker",
            "pytest",
            ["tests", "-q"],
            BACKEND,
            backend_env,
        )

        run_step(
            "3/3 - Tests administration",
            "pytest",
            ["tests", "-q"],
            ADMIN,
            admin_env,
        )

        print("\nTous les tests ont réussi !", flush=True)

    finally:
        print("\nArrêt et suppression du PostgreSQL de test...", flush=True)

        result = docker(
            "stop",
            "--time",
            "5",
            container_name,
            check=False,
        )

        if result.returncode == 0:
            print("Conteneur de test supprimé.", flush=True)
        else:
            print(
                "Attention : impossible de confirmer l'arrêt du conteneur.\n"
                f"{result.stderr}",
                flush=True,
            )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(
            f"\nÉchec d'une étape : code {error.returncode}",
            flush=True,
        )

        if error.stdout:
            print(f"STDOUT :\n{error.stdout}", flush=True)

        if error.stderr:
            print(f"STDERR :\n{error.stderr}", flush=True)

        sys.exit(error.returncode)
    except RuntimeError as error:
        print(f"\n{error}", flush=True)
        sys.exit(1)
