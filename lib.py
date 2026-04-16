import requests, os, sys, time, json, shutil
import re
import unicodedata
from difflib import get_close_matches
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Session globale pour maintenir les cookies de connexion
session = requests.Session()

COOKIES_FILE = "cookies.json"

def _build_browser_env():
    """Construit un environnement propre pour eviter les conflits Snap/GTK."""
    env = os.environ.copy()
    home = os.path.expanduser("~")

    env["HOME"] = home
    env.setdefault("XDG_CONFIG_HOME", os.path.join(home, ".config"))

    # Nettoie les variables souvent injectees par les apps Snap.
    for key in list(env.keys()):
        if key.startswith("SNAP"):
            env.pop(key, None)

    for key in ("GTK_PATH", "GTK_THEME", "GTK2_RC_FILES", "GTK_MODULES", "LD_PRELOAD"):
        env.pop(key, None)

    return env

def launch_playwright_browser(playwright):
    """Lance un navigateur Playwright avec plusieurs fallbacks robustes."""
    env = _build_browser_env()
    errors = []

    def _try(label, fn):
        try:
            print(f"🚀 Tentative: {label}")
            return fn()
        except Exception as e:
            msg = str(e).splitlines()[0]
            print(f"⚠️ Echec {label}: {msg}")
            errors.append((label, e))
            return None

    # 1) Firefox Playwright (navigateur telecharge par playwright install)
    browser = _try(
        "Firefox Playwright",
        lambda: playwright.firefox.launch(headless=False, env=env),
    )
    if browser:
        return browser

    # 2) Firefox systeme
    firefox_path = shutil.which("firefox")
    if firefox_path:
        browser = _try(
            f"Firefox systeme ({firefox_path})",
            lambda: playwright.firefox.launch(
                executable_path=firefox_path,
                headless=False,
                env=env,
            ),
        )
        if browser:
            return browser

    # 3) Chromium Playwright
    browser = _try(
        "Chromium Playwright",
        lambda: playwright.chromium.launch(headless=False, env=env),
    )
    if browser:
        return browser

    # 4) Chromium/Chrome systeme
    chromium_candidates = ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable"]
    for name in chromium_candidates:
        chromium_path = shutil.which(name)
        if not chromium_path:
            continue
        browser = _try(
            f"Chromium systeme ({chromium_path})",
            lambda p=chromium_path: playwright.chromium.launch(
                executable_path=p,
                headless=False,
                env=env,
            ),
        )
        if browser:
            return browser

    # 5) WebKit Playwright
    browser = _try(
        "WebKit Playwright",
        lambda: playwright.webkit.launch(headless=False, env=env),
    )
    if browser:
        return browser

    if errors:
        raise errors[-1][1]
    raise RuntimeError("Aucun navigateur Playwright disponible.")

def save_cookies():
    """Sauvegarde les cookies dans un fichier JSON."""
    try:
        cookies_dict = requests.utils.dict_from_cookiejar(session.cookies)
        with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies_dict, f)
        print(f"💾 Cookies sauvegardés dans {COOKIES_FILE}")
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder les cookies: {e}")

def load_cookies():
    """Charge les cookies depuis le fichier JSON."""
    if not os.path.exists(COOKIES_FILE):
        return False
    
    try:
        with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
            cookies_dict = json.load(f)
        
        for key, value in cookies_dict.items():
            session.cookies.set(key, value)
        
        print(f"🍪 {len(cookies_dict)} cookies chargés depuis {COOKIES_FILE}")
        return True
    except Exception as e:
        print(f"❌ Impossible de charger les cookies: {e}")
        return False

def requires_login(soup):
    """Détecte si la page demande une connexion."""
    text = soup.get_text().lower()
    keywords = ["tu dois être membre", "connexion", "authentification", "member only"]
    return any(keyword in text for keyword in keywords)

def handle_login(session, url):
    """
    Gère la connexion via formulaire AWeber.
    1. Essaie d'utiliser les cookies sauvegardés
    2. Si ça ne marche pas, lance Playwright pour se connecter
    3. Sauvegarde les nouveaux cookies
    """
    # Phase 1: Essaie les cookies sauvegardés
    print("🍪 Tentative avec les cookies sauvegardés...")
    if load_cookies():
        # Teste les cookies
        r = session.get(url, timeout=20)
        if "tu dois être membre" not in r.text.lower():
            print("✅ Cookies valides! Connexion reestablie.")
            return True
        else:
            print("⚠️ Cookies expirés, nouvelle connexion requise...")
    
    # Phase 2: Playwright pour nouvelle connexion
    if not PLAYWRIGHT_AVAILABLE:
        print("❌ Playwright n'est pas disponible et pas de cookies sauvegardés")
        return False
    
    print("🎭 Lancement de Playwright...")
    try:
        with sync_playwright() as p:
            print("🌐 Ouverture du navigateur...")
            browser = launch_playwright_browser(p)
            page = browser.new_page()
            page.set_default_timeout(15000)
            
            try:
                print(f"📄 Accès à la page...")
                page.goto(url, wait_until="domcontentloaded")
                print("✅ Page chargée")
                
                time.sleep(1)
                
                print("🔍 Recherche du formulaire cible af-body-1819031067...")

                target_block = page.locator("div#af-body-1819031067")
                target_count = target_block.count()

                if target_count > 0:
                    print("✅ Formulaire cible trouvé")
                    form_scope = target_block.first

                    # Remplit les champs demandes dans le bon bloc AWeber.
                    form_scope.locator("#awf_field-74946000").fill("paul")
                    form_scope.locator("#awf_field-74945999").fill("ppuubbss.bbiinn@gmail.com")

                    print("🔑 Envoi du formulaire cible...")
                    submit = form_scope.locator(
                        'button[type="submit"], input[type="submit"], button:has-text("OK"), input[value="OK"]'
                    )
                    if submit.count() > 0:
                        submit.first.click()
                    else:
                        # Fallback si le bouton n'est pas typé submit.
                        form_scope.locator("button, input").first.click()

                    print("⏳ Attente de la redirection...")
                    page.wait_for_timeout(3000)
                else:
                    print("⚠️ Formulaire cible introuvable, fallback générique...")
                    has_login_form = False
                    try:
                        page.fill('input[name="email"], input[type="email"]', "ppuubbss.bbiinn@gmail.com")
                        has_login_form = True
                        print("✅ Champ email trouvé")
                    except:
                        print("❌ Pas de champ email de login")

                    if has_login_form:
                        try:
                            page.fill('input[name="password"], input[type="password"]', "ppuubbss.bbiinn@gmail.com")
                            print("✅ Champ mot de passe trouvé")
                        except:
                            print("ℹ️ Pas de champ mot de passe (peut-être juste email)")

                        print("🔑 Envoi du formulaire de connexion...")
                        try:
                            page.click('button:has-text("Se connecter"), button:has-text("Connexion"), input[value="Connexion"]')
                        except:
                            page.click('button')

                        print("⏳ Attente de la redirection...")
                        page.wait_for_timeout(3000)
                    else:
                        print("📝 Formulaire d'inscription détecté, remplissage...")
                        page.fill('input[name="name"]', "paul")
                        page.fill('input[name="email"]', "ppuubbss.bbiinn@gmail.com")

                        try:
                            page.select_option('select[name="custom classe"]', "Enseignant")
                        except:
                            pass

                        print("🔑 Envoi du formulaire...")
                        page.click('button:has-text("OK"), input[value="OK"]')

                        print("⏳ Attente du CAPTCHA...")
                        print("   Résolvez le CAPTCHA manuellement si nécessaire")
                        input("⏸️  Appuyez sur ENTRÉE après avoir complété le CAPTCHA... ")
                        page.wait_for_timeout(2000)
                
                # Vérification
                page_text = page.content()
                if "tu dois être membre" in page_text.lower():
                    print("⚠️ Connexion échouée, le formulaire est toujours présent")
                    return False
                
                # Récupération des cookies
                print("🍪 Récupération des cookies...")
                cookies = page.context.cookies()
                for cookie in cookies:
                    session.cookies.set(cookie['name'], cookie['value'])
                
                save_cookies()
                print("✅ Connexion réussie! Cookies sauvegardés.")
                return True
                
            finally:
                browser.close()
                
    except Exception as e:
        print(f"❌ Erreur Playwright: {e}")
        import traceback
        traceback.print_exc()
        return False

def print_logo():
    # logo fr-scrap
    print("""
███████╗██████╗       ███████╗ ██████╗██████╗  █████╗ ██████╗
██╔════╝██╔══██╗      ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗
█████╗  ██████╔╝█████╗███████╗██║     ██████╔╝███████║██████╔╝
██╔══╝  ██╔══██╗╚════╝╚════██║██║     ██╔══██╗██╔══██║██╔═══╝
██║     ██║  ██║      ███████║╚██████╗██║  ██║██║  ██║██║
╚═╝     ╚═╝  ╚═╝      ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  
    """)

def print_text():
    print("""
fr-scrap est un outil de scraping pour trouver des infos pour les fiches de révison de français.
Veuillez report les bugs sur github : https://github.com/ZRS40/fr-scrap
\nQue voulez-vous faire ?
1) Récupérer les fiches de lectures d'une œuvre
2) Récupérer des analyses de lectures linéaires
""")

def get_info():
    """Point d'entree conserve pour compatibilite avec main.py."""
    print("ℹ️ Cette option n'est pas encore implémentée.")
    print("Utilisez l'option 2 pour recuperer et parcourir les analyses disponibles.")

def get_lect():
    url = "https://commentairecompose.fr/commentaires-composes/"
    print("📥 Téléchargement des analyses de lectures linéaires...")
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    
    with open("analyses_lectures_lineaires.txt", "w", encoding="utf-8") as f:
        f.write(r.text)
    
    print("✅ Analyses de lectures linéaires téléchargées et sauvegardées.")

def get_lect_dict(path="analyses_lectures_lineaires.txt"):
    # Télécharge si le fichier n'existe pas ou si la dernière modification date de plus de 7 jours
    if not os.path.exists(path):
        get_lect()
    elif (time.time() - os.path.getmtime(path)) > 7 * 24 * 3600:
        get_lect()

    with open(path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    zone = soup.select_one("article#post-3759 .entry-content") or soup
    out, current_author = {}, None

    for tag in zone.select("h2,h3,p,li"):
        txt = tag.get_text(" ", strip=True)

        if tag.name in ("h2", "h3") and "»" in txt and ":" in txt:
            current_author = txt.split("»", 1)[1].split(":", 1)[0].strip()
            out.setdefault(current_author, [])
            continue

        if not current_author:
            continue

        for a in tag.select("a[href]"):
            titre = a.get_text(" ", strip=True)
            lien = a["href"].strip()
            if not titre or not lien:
                continue
            if any(x["lien"] == lien for x in out[current_author]):
                continue
            out[current_author].append({"titre": titre, "lien": lien})

    return out

def print_lect_dict(d):
    for auteur, textes in d.items():
        print(f"\n## {auteur} ({len(textes)})")
        for t in textes:
            print(f"- {t['titre']} -> {t['lien']}")

def list_authors(d):
    return list(d.keys())

def print_authors(authors):
    print("\nAuteurs disponibles :")
    print(" | ".join(f"{i}) {a}" for i, a in enumerate(authors, 1)))

def resolve_author(authors, value):
    s = value.strip()
    if not s:
        return None

    if s.isdigit():
        i = int(s) - 1
        return authors[i] if 0 <= i < len(authors) else None

    s_low = normalize_search_text(s)
    for a in authors:
        if normalize_search_text(a) == s_low:
            return a

    # Prefix explicite (utile pour une saisie partielle d'auteur).
    if len(s_low) >= 3:
        for a in authors:
            a_low = normalize_search_text(a)
            if a_low.startswith(s_low):
                return a

    # Fuzzy strict pour corriger une petite faute de frappe sans faux positifs.
    author_keys = [normalize_search_text(a) for a in authors]
    matches = get_close_matches(s_low, author_keys, n=1, cutoff=0.85)
    if matches:
        for a in authors:
            if normalize_search_text(a) == matches[0]:
                return a
    
    return None

def normalize_search_text(text):
    """Normalise une chaine pour la recherche (accents, casse, ponctuation)."""
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized

def search_text_by_title(d, search_term):
    """
    Recherche un texte par titre dans tous les auteurs.
    Retourne une liste de tuples (auteur, texte) en matching simple sur le titre.
    """
    query = normalize_search_text(search_term)
    if not query:
        return []

    query_tokens = [t for t in query.split() if t]
    results = []
    for auteur, textes in d.items():
        for texte in textes:
            titre_norm = normalize_search_text(texte["titre"])
            if query in titre_norm:
                # Match direct de la requete complete.
                rank = (0, titre_norm.find(query), len(titre_norm))
                results.append((rank, auteur, texte))
                continue

            if query_tokens and all(token in titre_norm for token in query_tokens):
                # Match sur tous les mots de la requete, meme non contigus.
                first_pos = min(titre_norm.find(token) for token in query_tokens)
                rank = (1, first_pos, len(titre_norm))
                results.append((rank, auteur, texte))

    results.sort(key=lambda x: (x[0], x[2]["titre"]))
    return [(auteur, texte) for _, auteur, texte in results[:20]]

def print_author_texts(d, author):
    textes = d.get(author, [])
    print(f"\n## {author} ({len(textes)})")
    for i, t in enumerate(textes, 1):
        print(f"{i}) {t['titre']}")

def scrape_and_print_text(url, titre):
    # Nettoie le titre pour le nom de fichier
    nom_fichier = "".join(c for c in titre if c.isalnum() or c in (" ", "-", "_")).rstrip()
    nom_fichier = nom_fichier.replace(" ", "_")

    if os.path.exists(f"files/{nom_fichier}.txt") or os.path.exists(f"files\\{nom_fichier}.txt"):
        print(f"📂 Le texte '{titre}' a déjà été téléchargé.")
        open_file(nom_fichier)
        return
    
    r = session.get(url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    
    # Vérifie si connexion requise
    if requires_login(soup):
        print("🔐 Connexion requise...")
        if not handle_login(session, url):
            print("❌ Connexion échouée ou non configurée.")
            return
        
        # Retry après connexion
        print("🔄 Nouvelle tentative de scraping...")
        r = session.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    
    main = soup.find("main", {"id": "main"})
    
    if not main:
        print("❌ Impossible de récupérer le contenu.")
        return
    
    for br in main.find_all("br"):
        br.replace_with("\n")

    if not os.path.exists("files"):
        os.makedirs("files")

    open_file(nom_fichier, main)

def open_file(nom_fichier, main=None):
    if sys.platform == "linux":
        filepath = f"files/{nom_fichier}.txt"
        if main:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(main.get_text()[3:])
            print(f"✅ Texte sauvegardé dans {filepath}")
        os.system(f"xdg-open {filepath}")
    elif sys.platform == "win32":
        filepath = f"files\\{nom_fichier}.txt"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(main.get_text()[3:])
        print(f"✅ Texte sauvegardé dans {filepath}")
        os.system(f"start {filepath}")
