import requests
from bs4 import BeautifulSoup, NavigableString

def scrape_n64_titles():
    """
    Goes through the wikipedia page of N64 games and writes them
    all to a file n64.txt

    """
    # URL of the wikipedia page
    url = "https://en.wikipedia.org/wiki/List_of_Nintendo_64_games"

    # Send a GET request to the page
    response = requests.get(url)
    # Parse the HTML content with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the table containing the game titles 
    tables = soup.find_all("table", {"class": "wikitable"})

    # Empty list to store game titles
    game_titles = []

    # Loop through each table to extract titles
    for table in tables:
        # Checks to see if the table has title or game header
        headers = [th.text.strip() for th in table.find_all("th")]
        if not any("Title" in h or "Game" in h for h in headers):
            continue  
        # Find all rows in the table
        rows = table.find_all("tr")
        # Loop through each row, skipping the header row
        for row in rows[1:]:
            # Find all cells in the row
            cells = row.find_all("td")
            if cells:
                cell = cells[0]
                italics = cell.find_all("i")
                # First italic is title
                if italics:
                    main_title = italics[0].text.strip()
                    alt_titles = []

                    # Other italics are alt titles
                    for i_tag in italics[1:]:
                        alt_title = i_tag.text.strip()

                        # Look for the <sup> tag immediately after this <i>
                        next_elem = i_tag.next_sibling
                        region = ""
                        while next_elem and (isinstance(next_elem, NavigableString) or next_elem.name != "sup"):
                            next_elem = next_elem.next_sibling
                        if next_elem and next_elem.name == "sup":
                            region = next_elem.text.strip()

                        alt_titles.append(f"{region}: {alt_title}")

                    if alt_titles:
                        main_title += " " + " ".join(f"({t})" for t in alt_titles)

                    game_titles.append(main_title)
        break # Stops after finding first relevant table

    # Write game titles to N64.txt
    with open("N64.txt", "w", encoding="utf-8") as file:
        for title in game_titles:
            file.write(title + "\n")
