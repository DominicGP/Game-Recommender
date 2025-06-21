import requests, re, time
import difflib
from bs4 import BeautifulSoup
from selenium import webdriver
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException
from collections import OrderedDict

# PRIVATE API KEY
GIANT_BOMB_API_KEY = "your_api_key_here"

def get_wikipedia_url(main_title):
    """
    Uses the game title and wikipedia API to try and find a wikipedia page for said game title

    Args:
        main_title (str): The main title of the game

    Returns:
        str: wikipedia page url if found
    """
    # Use wikipedia's API to search for the title
    search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={main_title}&format=json"
    response = requests.get(search_url)
    data = response.json()

    # Finds the best matching wikipedia page for the given games main title
    if "query" in data and "search" in data["query"] and data["query"]["search"]:
        results = data["query"]["search"]
        titles = [result["title"] for result in results]

        # Filter to prefer pages with '(video game)' in the title
        preferred = [t for t in titles if "video game" in t.lower()]
        # Sort pages by most smiliar to game title
        if preferred:
            preferred_sorted = sorted(
                preferred,
                key=lambda t: difflib.SequenceMatcher(None, main_title.lower(), t.lower()).ratio(),
                reverse=True
            )
            top_match = preferred_sorted[0]
            score = difflib.SequenceMatcher(None, main_title.lower(), top_match.lower()).ratio()
        
            # Only accept the top preferred match if similarity is high enough
            if score > 0.60:
                page_title = top_match
            else:
                # Fall back to all titles if no good match in preferred
                # Requires good match regardless
                best_match = difflib.get_close_matches(main_title, titles, n=1, cutoff=0.8)
                if best_match:
                    page_title = best_match[0]  
                else:
                    return None
        else:
            # No preferred matches; use closest match from all titles
            # Requires good match regardless
            best_match = difflib.get_close_matches(main_title, titles, n=1, cutoff=0.8)
            if best_match:
                    page_title = best_match[0]  
            else:
                return None

        return f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"

    return None

def clean_text(soup_element):
    """
    Takes a value element from a wikipedia credits table row, and extracts the text

    Args:
        soup_element (Tag): A BeautifulSoup element (e.g., <td>) containing credits information.

    Returns:
        list: a cleaned list of text elements extracted from the element
    
    """

    # Gets text from elements using a custom seperator
    text = soup_element.get_text(separator=" || ", strip=False)
    parts = [part.strip() for part in text.split(" || ") if part.strip()]

    cleaned = []
    i = 0

    # Clean text parts
    while i < len(parts):
        part = parts[i].strip()

        # Combines colons with items before and after it 
        # Ex. NA, :, Activision -> NA: Activision
        if part == ":" and i > 0 and i + 1 < len(parts):
            prev = cleaned.pop()  # Remove last added item
            next_part = parts[i + 1].strip()
            combined = f"{prev}: {next_part}"
            cleaned.append(combined)
            i += 2  # Skip over next part

        # Combines current bracket term with previous term
        # Ex. Activision, (PAL) -> Activision (PAL)
        elif part.startswith("(") and part.endswith(")"):
            prev = cleaned.pop()  # Remove last added item
            combined = f"{prev} {part}"
            cleaned.append(combined)
            i += 1
        # Skips terms if length is 1 Ex. 1 or [ 
        elif len(part) == 1:
            i+=1 
            continue
        # Add regular part
        else:
            if part:
                cleaned.append(part)
            i += 1

    return cleaned

def get_wikipedia_info(game_title):
    """
    Takes the game title and attempts to find a wikipedia article for it,
    which is then used to scrape data from for the database

    Args:
        game_title (str): The title of the game

    Returns:
        wikipedia_info (dict): information about the game title:
            - 'Publisher' (str): Publisher(s) of the game
            - 'Developer' (str): Developer(s) of the game
            - 'Title' (str): Title of the game
            - 'Alt-Titles' (str): Alternate titles of the game
            - 'Director' (str): Director(s) of the game
            - 'Artist' (str): Artist(s) of the game
            - 'Writer' (str): Writer(s) of the game
            - 'Composer' (str): Composer(s) of the game
            - 'Genre' (str): Genre(s) of the game
            - 'Aggregate Score' (str): Gamerankings/Metacritic score of the game
 
    """

    # Done so we can use main title to search/scrape
    main_title = game_title.split("(", 1)[0].strip()
    alt_titles = "(" + game_title.split("(", 1)[1].strip() if "(" in game_title else ""

    # Dictionary to store game details
    wikipedia_info = {
        'Publisher': None,
        'Developer': None,
        'Title': main_title,
        'Alt-Titles': alt_titles,
        'Director': None,
        'Artist': None,
        'Writer': None,
        'Composer': None,
        'Genre': None,
        'Aggregate Score': None
    }

    # Get Wikipedia URL using the Wikipedia API
    wiki_url = get_wikipedia_url(main_title)
    if not wiki_url:
        print(f'Failed to find wikipedia page for: {game_title}')
        return wikipedia_info
    
    print(f"Found wikipedia page for {game_title} at: {wiki_url}")
    # Request the Wikipedia page for the game
    response = requests.get(wiki_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the credits table and extract relevant fields
    infobox = soup.find("table", {"class": "infobox"})
    if infobox:
        # Loop through each row in the credits table
        for row in infobox.find_all("tr"):
            header = row.find("th")
            value = row.find("td")
            if header and value:
                header_text = header.text.strip()
                clean_value_text = clean_text(value)
                if "Publisher" in header_text:
                    # Checks to see if there is a specific N64 publisher for formatting reasons
                    if "Nintendo 64" in clean_value_text:
                        idx = clean_value_text.index("Nintendo 64")
                        # Assumes that the text after Nintendo 64 is the publisher
                        if idx + 1 < len(clean_value_text):
                            wikipedia_info['Publisher'] = clean_value_text[idx + 1]
                            continue
                    # Checks to see if there is a specific N64 publisher with the bracket tag (N64)
                    elif any("(N64)" in item for item in clean_value_text):
                        index = next(i for i, item in enumerate(clean_value_text) if "(N64)" in item)
                        wikipedia_info['Publisher'] = clean_value_text[index][:-6]
                        continue

                    publishers = []
                    # Loops through publishers if there are multiple
                    for publisher in clean_value_text :
                        # Formats publishers if they're region specific
                        # Ex. NA: THQ -> THQ (NA), ...
                        if ":" in publisher:
                            region, name = publisher.split(":", 1)
                            publishers.append(f"{name.strip()} ({region.strip()})")
                        else:
                            publishers.append(publisher)
                    wikipedia_info['Publisher'] = ", ".join(publishers)
                elif "Developer" in header_text:
                        developers = []
                        # Loops through developers
                        for developer in clean_value_text:
                            # Try to find a specified N64 developer
                            if developer.endswith("(N64)"):
                                # Removes (N64) tag
                                wikipedia_info['Developer'] = developer[:-6]
                                break
                            # Skips developers tagged with other platforms in brackets (e.g., "(PS1)")
                            elif not re.search(r"\([^\)]*\)$", developer): 
                                developers.append(developer)
                        if developers:
                            wikipedia_info['Developer'] = ", ".join(developers)
                elif "Director" in header_text:
                    wikipedia_info['Director'] = ", ".join(clean_value_text)
                elif "Artist" in header_text:
                    wikipedia_info['Artist'] = ", ".join(clean_value_text)
                elif "Writer" in header_text:
                    wikipedia_info['Writer'] = ", ".join(clean_value_text)
                elif "Composer" in header_text:
                    wikipedia_info['Composer'] = ", ".join(clean_value_text)
                elif "Genre" in header_text:
                    wikipedia_info['Genre'] = ", ".join(clean_value_text)

    # Check for Metacritic or GameRankings score in the Reception section
    wikipedia_info['Aggregate Score'] = get_score_from_reception(soup)

    return wikipedia_info

def get_score_from_reception(soup):
    """
    Attempts to find an aggregate score in the wikipedia page

    Args:
        soup (BeautifulSoup): Parsed wikipedia page

    Returns:
        str: Aggregate score of the given game
    """
    # Tries to find the reception header
    reception_header = soup.find(id="Reception") or soup.find(id="reception")
    if not reception_header:
        print("Reception section not found.")
        return None

    # Tries to find the reception table
    table = reception_header.find_next("table")

    # Makes sure the next table isn't a stub
    if not table or table.get("role") == "presentation" :
        print("No table found after Reception.")
        return None

    # Finds the rows in the table
    rows = table.find_all("tr")
    # Get text from tables second row
    second_row_cells = [cell.get_text(strip=True) for cell in rows[1].find_all(["td", "th"])]

    # When there are console columns, the row underneath contains the score
    try: 
        # Checks to see if N64 is a column
        n64_index = second_row_cells.index("N64")

        # Goes to the row underneath and extracts the score value
        if len(rows) > 2:
            score_cells = rows[2].find_all(["td", "th"])
            if len(score_cells) > n64_index:
                score_text = score_cells[n64_index + 1].get_text()
                match = re.search(r"\b\d{1,3}(?:\.\d{1,2})?(?=%|/100)", score_text) # Match numbers like 85, 85.3, or 85.32 followed by % or /100
                if match:
                    return match.group()
    except ValueError:
        pass
    
    # If no console column, scan remaining rows for aggregate scores
    for row in rows[1:]:
        cell_text = []
        for cell in row.find_all(["td", "th"]):
            # Remove <sup> citation tags before matching
            for sup in cell.find_all("sup"):
                sup.decompose()
            
            cell_text.append(cell.get_text())

        # Skip rows that don't mention known aggregate sources
        if "Metacritic" not in cell_text and 'GameRankings' not in cell_text:
            print("No aggregate score")
            return None


        # Checks to see if there is a N64 specific score
        # For some reason some pages don't use console columns, instead all scores are in the same column
        match = re.search(r'\(N64\)\s*\d+(\.\d+)?%', cell_text[-1])

        # If N64 score found
        if match:
            match = match.group()
            score = re.search(r"\b\d{1,3}(?:\.\d{1,2})?(?=%|/100|\b)", match) # Match numbers like 85, 85.3, or 85.32 followed by % or /100
            print(f"Score found: {score.group()}")
            return score.group()

        # If no console specific score
        if cell_text:
            score = re.search(r"\b\d{1,3}(?:\.\d{1,2})?(?=%|/100|\b)", cell_text[-1]) # Match numbers like 85, 85.3, or 85.32 followed by % or /100
            if score:
                print(f"Score found: {score.group()}")
                return score.group()
            
    return None

def search_giant_bomb_game(game_title):
    """
    Takes the given game title and attempts to find a giantbomb
    page for it using their API

    Args:
        game_title (str): Title of the game

    Returns:
        str: unique game id in the Giantbomb API
    """
    # Strip alternate titles in parentheses (e.g., "Title (Alt)") to focus on main title
    main_title = game_title.split("(", 1)[0].strip()

    # Use the Giant Bomb API to search for the game by title
    search_url = "https://www.giantbomb.com/api/search/"
    params = {
        "api_key": GIANT_BOMB_API_KEY,
        "format": "json",
        "query": main_title,
        "resources": "game"
    }
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(search_url, headers=headers, params=params)
    data = response.json()

    # Check if there are any results
    if "results" in data and data["results"]:
        for game_data in data["results"]:
            platforms = [p["name"] for p in game_data.get("platforms") or []]
            # Makes sure its an N64 game
            if "Nintendo 64" in platforms:
                print(f'Found giantbomb page for: {game_title}')
                return game_data["guid"]

    # If it can't find a giantbomb page 
    print(f'Failed to find giantbomb page for: {game_title}')

    return None

def get_giant_bomb_game_details(guid):
    """
    After finding the game titles ID in the giantbomb database, attempt
    to scrape data about the game 

    Args:
        guid (str): Unique gameid for said game in the Giantbomb database

    Returns:
        giant_bomb_info (dict): Giantbomb information about the game:
            - 'Publisher' (str): Publisher(s) of the game
            - 'Developer' (str): Developer(s) of the game
            - 'Theme' (str): Theme(s) of the game
            - 'Franchise' (str): Game Franchise(s)
            - 'Genre' (str): Genre(s) of the game
    """
    # Retrieve detailed game information using the Giant Bomb API game endpoint
    game_url = f"https://www.giantbomb.com/api/game/{guid}/"
    params = {
        "api_key": GIANT_BOMB_API_KEY,
        "format": "json"
    }
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(game_url, headers=headers, params=params)
    data = response.json()

    # Extract the relevant fields from the response. Should only be one result due to unique game ID
    if "results" in data:
        game_details = data["results"]
        giant_bomb_info = {

            "Publisher": ", ".join(publisher["name"] for publisher in game_details.get("publishers") or []),
            "Developer": ", ".join(developer["name"] for developer in game_details.get("developers") or []),
            "Theme": ", ".join(theme["name"] for theme in game_details.get("themes") or []),
            "Franchise": ", ".join(franchise["name"] for franchise in game_details.get("franchises") or []),
            "Genre": ", ".join(genre["name"] for genre in game_details.get("genres") or [])
        }
        return giant_bomb_info
    else:
        print("No detailed game information found.")
        return None

def mobygames_credits(game_title):
    """
    Takes the given game title and attempts to find a mobygames page
    for it, if successful try to find relevant credits for the game

    Args:
        game_title (str): Title of the game

    Returns:
        mobygames_info (dict): Mobygames information about the game:
            - 'Director' (str): Director(s) of the game
            - 'Artist' (str): Artist(s) of the game
            - 'Writer' (str): Writer(s) of the game
            - 'Composer' (str): Composer(s) of the game
    """
    # Map of standardized roles to keywords, ordered by priority (first match wins)
    role_map = OrderedDict({
    'Director': ["Director", "Directors", "Game Director", "Project Leader", "Planning"],
    'Artist': ["Art Director", "Art Direction", "Visual Direction", "Visual Director", "Lead Artist", "Artists", "Character Design"],
    'Writer': ["Writer", "Writers", "Backstory & Script", "Scenario"],
    'Composer': ["Music", "Composer", "Music Composer", "Sound Composer", "Music Composition", "Sound / Music", "BGM Composer", "Music/Sound Effects", "Lead Musician"]
    })

    # Split so we only use the main title
    main_title = game_title.split("(", 1)[0].strip()
    moby_link = None
    query = f"mobygames {main_title}"
    # Use DuckDuckGo search to see if there is a mobygames page for the game
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=5)
            for result in results:
                # If we find a mobygames page, add the credits and N64 format to the link
                if "mobygames.com" in result['href']:
                    moby_link = result['href'] + "credits/n64/"
                    break
    # DuckDuckGo ratelimit is undefined/random and I could not find a workaround for this
    except DuckDuckGoSearchException:
        print("Ratelimit error, could not find a reason or fix for this  ")
    
    # If we cant find a mobygames
    if not moby_link:
        print(f"Failed to find mobygames page for: {game_title}")
        return None
    
    print(f"Found mobygames page for: {game_title}")

    # Request the Mobygames page
    driver = webdriver.Firefox() 
    driver.get(moby_link)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    # Find credits table
    credits = soup.find("table", class_="table-credits")

    # Roles we're looking for
    mobygames_info = {
        'Director': None,
        'Artist': None,
        'Writer': None,
        'Composer': None
    }

    credits_data = {}

    # Loop through credits table
    if credits:
        # Loop through each row in the table
        for row in credits.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                # Get the job title, always first cell in row
                job_title = cells[0].get_text(strip=True)

                # Get all linked people in the second cell
                people_links = cells[1].find_all("a")
                people = [a.get_text(strip=True) for a in people_links]
                people_text = ", ".join(people)

                credits_data[job_title] = people_text
    
    assigned_priorities = {role: float("inf") for role in role_map}  # Track best (lowest) priority seen

    # Loop through every found credit
    for key, value in credits_data.items():
        # Lowercase and clean roles
        key_clean = key.strip().lower()
        # Loop through rolemap 
        for priority, (role, keywords) in enumerate(role_map.items()):
            # Lowercase role search terms
            normalized_keywords = [k.lower() for k in keywords]
            # If we find a matching role and its priority is higher (i.e., lower number), update it
            if key_clean in normalized_keywords:
                if priority < assigned_priorities[role]:
                    mobygames_info[role] = value
                    assigned_priorities[role] = priority
                break  # Don't check lower-priority roles

        
    return mobygames_info

def get_combined_game_info(game_title):
    """
    Takes game title and runs it through multiple auxiliary functions to scrape
    data from Giantbomb/Wkipedia/Mobygames

    Args:
        game_title (str): title of the game we want to find

    Returns:
        combined_info (dict): combined information about the game title:
            - 'Publisher' (str): Publisher(s) of the game
            - 'Developer' (str): Developer(s) of the game
            - 'Title' (str): Title of the game
            - 'Alt-Titles' (str): Alternate titles of the game
            - 'Director' (str): Director(s) of the game
            - 'Artist' (str): Artist(s) of the game
            - 'Writer' (str): Writer(s) of the game
            - 'Composer' (str): Composer(s) of the game
            - 'Genre' (str): Genre(s) of the game
            - 'Aggregate Score' (str): Gamerankings/Metacritic score of the game
            - 'Theme' (str): Theme(s) of the game
    
    """
    # Wikiepdia scraping
    wikipedia_info = get_wikipedia_info(game_title)

    # Giantbomb scraping, has a rate limit of 200/hour. 
    # Means one call every 18 second, or one game every 36
    print("\nSleep 1 for 18 seconds")
    time.sleep(18)
    guid = search_giant_bomb_game(game_title)
    print("\nSleep 2 for 18 seconds \n")
    time.sleep(18)
    giant_bomb_info = get_giant_bomb_game_details(guid) if guid else {}

    # Mobygames scraping
    mobygames = mobygames_credits(game_title)

    # Initialize unified information
    combined_info = wikipedia_info if wikipedia_info else {}
    
    # Add Giant Bomb info, check to see if there is any existing info
    if giant_bomb_info:
        for title, info in giant_bomb_info.items():
            # When combining Genre or Themes check to see if any new ones are discovered
            if title in ("Genre", "Theme"):
                existing = combined_info.get(title, "")
                existing_parts = [part.strip() for part in (existing or "").split(",") if part.strip()]
                new_parts = [part.strip() for part in info.split(",") if part.strip()]
                # Loops through new data to see if its not already included
                for part in new_parts:
                    if part not in existing_parts:
                        existing_parts.append(part)

                combined_info[title] = ", ".join(existing_parts)
            else:
                if not combined_info.get(title):
                    combined_info[title] = info

    # Add mobygames info, keeping existing info
    if mobygames:
        for job, people in mobygames.items():
            if not combined_info.get(job):  
                combined_info[job] = people



    return combined_info
