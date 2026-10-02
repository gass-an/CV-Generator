import getpass

from argon2 import PasswordHasher


def main() -> None:
    """Génère un hash Argon2id sans afficher le mot de passe."""
    password = getpass.getpass("Mot de passe administrateur : ")
    confirmation = getpass.getpass("Confirmez le mot de passe : ")
    if not password or password != confirmation:
        raise SystemExit("Les mots de passe sont vides ou différents.")
    print(PasswordHasher().hash(password))


if __name__ == "__main__":
    main()
