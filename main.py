import sys, os, lib

def clear():
    os.system("clear" if os.name != "nt" else "cls")

clear()
lib.print_logo()
lib.print_text()

choice = input("Entrez votre choix : ")
if choice == "1":
    clear()
    lib.get_info()
elif choice == "2":
    clear()
    d = lib.get_lect_dict()

    if not d:
        print("❌ Aucun auteur trouvé.")
        sys.exit(1)

    authors = lib.list_authors(d)
    print("\nAuteurs disponibles :")
    print("0) Chercher un texte en particulier")
    print(" | ".join(f"{i}) {a}" for i, a in enumerate(authors, 1)))
    
    selected = input("\nSélectionnez un auteur (0 pour chercher, numéro ou nom) : ")
    
    # Option 0: Chercher un texte
    if selected == "0":
        clear()
        search_term = input("📝 Entrez le titre ou une partie du titre du texte : ")
        results = lib.search_text_by_title(d, search_term)
        
        if not results:
            print(f"❌ Aucun texte trouvé pour '{search_term}'")
            sys.exit(1)
        
        print(f"\n✅ {len(results)} résultat(s) trouvé(s):\n")
        for idx, (auteur, texte) in enumerate(results, 1):
            print(f"{idx}) {texte['titre']} - {auteur}")
        
        selected_text = input("\nSélectionnez un texte (numéro) : ")
        
        if selected_text.isdigit():
            idx = int(selected_text) - 1
            if 0 <= idx < len(results):
                auteur, texte = results[idx]
                clear()
                print(f"🔨 Scrapping : {texte['titre']}...\n")
                lib.scrape_and_print_text(texte['lien'], texte['titre'])
            else:
                print("❌ Texte invalide.")
                sys.exit(1)
        else:
            print("❌ Entrée invalide.")
            sys.exit(1)
    else:
        # Résolution classique par auteur
        author = lib.resolve_author(authors, selected)

        if not author:
            print("❌ Auteur invalide.")
            sys.exit(1)

        clear()
        lib.print_author_texts(d, author)
        
        textes = d.get(author, [])
        selected_text = input("\nSélectionnez un texte (numéro) : ")
        
        if selected_text.isdigit():
            idx = int(selected_text) - 1
            if 0 <= idx < len(textes):
                clear()
                print(f"🔨 Scrapping : {textes[idx]['titre']}...\n")
                lib.scrape_and_print_text(textes[idx]['lien'], textes[idx]['titre'])
            else:
                print("❌ Texte invalide.")
                sys.exit(1)
        else:
            print("❌ Entrée invalide.")
            sys.exit(1)
else:
    print("❌ Choix invalide, veuillez réessayer.")
    sys.exit(1)
