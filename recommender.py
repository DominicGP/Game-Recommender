import openpyxl
import os, re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import difflib
import tkinter as tk

def clean_text(text):
    """
    Takes the data from the worksheet and normalizes names by replacing spaces with underscores 
    (e.g., John Smith → John_Smith) and removing region tags like (NA).
    Args:
        text (str): data from the worksheet, multiple entries are split by commas
    Returns:
        str: Cleaned string with spaces replaced by underscores and region codes removed
    """
    # If no text
    if not text:
        return ""
    # Removes trailing region codes Ex. (NA) specific to publishers
    text = re.sub(r"\s*\(.*?\)", "", text)
    # Removes spaces with _, removes commas 
    return " ".join(v.replace(" ", "_") for v in text.split(", "))

def prepare_dataset():
    """
    Takes the data from the worksheet and creates a dataframe with it

    Returns:
        pandas.DataFrame: Dataframe of the workbook data
    """
    # If no Excel file exists, return empty dataframe
    if not os.path.isfile("games.xlsx"):
        return pd.DataFrame()
    # Open workbook
    wb = openpyxl.load_workbook("games.xlsx")
    ws = wb.active

    # Columns of the workbook
    columns = {
        "Title": [],
        "Publisher": [],
        "Developer": [],
        "Director": [],
        "Artist": [],
        "Writer": [],
        "Composer": [],
        "Genre": [],
        "Score": [],
        "Theme": [],
        "Franchise": []
    }

    # Loop through each row in workbook and add value to respective list
    for row in ws.iter_rows(min_row=2, values_only=True):
        columns["Title"].append(row[1]) # Column 0 is platform, which is not needed
        columns["Publisher"].append(clean_text(row[3]))
        columns["Developer"].append(clean_text(row[4]))
        columns["Director"].append(clean_text(row[5]))
        columns["Artist"].append(clean_text(row[6]))
        columns["Writer"].append(clean_text(row[7]))
        columns["Composer"].append(clean_text(row[8]))
        columns["Genre"].append(clean_text(row[9]))
        columns["Score"].append(row[10])
        columns["Theme"].append(clean_text(row[11]))
        columns["Franchise"].append(clean_text(row[12]))
    
    return pd.DataFrame(columns)

def rec_engine(given_games, excluded_franchises=None):
    """
    Takes the user input and returns a list of top recommended games
    based on similarity to the inputted titles

    Args:
        given_games (list): list of user inputted games
        excluded_franchises (list): List of excluded franchises
    
    Returns:
        list: list of top 10 recommendations by cosine similarity after filtering
    """
    # Create dataframe
    dataset = prepare_dataset()

    # If bad dataframe return nothing
    if dataset.empty or "Title" not in dataset.columns:
        print("Dataset is empty or malformed.")
        return []
    
    # Weights assigned to the respective fields in the dataframe
    score_weight = 0.15
    # Should total to a value of 1 - score weight
    weights = {
        "Genre": 0.3,
        "Developer": 0.1394,
        "Director": 0.1046,
        "Publisher": 0.1046,
        "Theme": 0.0697,
        "Composer": 0.0489,
        "Artist": 0.035,
        "Writer": 0.0178
    }

    # Map games titles to index number
    title_to_index = {t: i for i, t in enumerate(dataset["Title"])}
    # Makes sure given games are actual N64 games
    valid_games = []
    for title in given_games:
        if title in title_to_index:
            valid_games.append(title)
    

    # If no valid games given return early
    if not valid_games:
        print("No valid game titles provided.")
        return []
    
    # Finds index values for all given games
    indices = [title_to_index[t] for t in valid_games]
    # Creates zero array for combined similarity scores
    combined_similarity = np.zeros(len(dataset))

    # Change scores values to numeric
    dataset["Score"] = pd.to_numeric(dataset["Score"], errors="coerce")
    # Fill empty scores with the mean score
    dataset["Score"] = dataset["Score"].fillna(dataset["Score"].mean())
    # Normalize aggregate scores
    normalized_scores = (dataset["Score"] - dataset["Score"].min()) / (dataset["Score"].max() - dataset["Score"].min())

    # Loop through each column field and their weights
    for column, weight in weights.items():
        # Fill missing values with empty strings
        texts = dataset[column].fillna("").astype(str)
        # Create TF-IDF scores
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(texts)
        # Find the average TF-IDF of the given games
        avg_vector = np.mean(tfidf_matrix[indices], axis=0)
        # Compares given games average to every other game
        similarity = cosine_similarity(np.asarray(avg_vector), tfidf_matrix).flatten()
        # Combines the similarity scores and multiples the field by its weight
        combined_similarity += weight * similarity

    # Add the normalized score/weight to the combined similarity 
    combined_similarity += score_weight * normalized_scores.to_numpy()

    # Creates a set of indices for the given games
    exclude_indices = set(indices)
    # Sorts games based on similarity score descendingly 
    all_indices = np.argsort(combined_similarity)[::-1]
    # Filters out given games from the recommendation set.
    # Also prevents excluded franchises from showing
    filtered = []
    for i in all_indices:
        if i in exclude_indices:
            continue
        franchises = dataset.loc[i, "Franchise"].split()
        if excluded_franchises and any(f in excluded_franchises for f in franchises):
            continue
        filtered.append(i)
    # Gets the titles of the top 10 recommended games
    recommendations = dataset["Title"].iloc[filtered[:10]].tolist()

    return recommendations

def suggest_title_correction(root, bad_title, all_titles, input_box, line):

    """
    Takes a game title from the user that couldn't be found in the avaliable games
    and then tries to find the most similar one as a correction

    Args:
        root (tk): GUI root of the program
        bad_title (str): title given by the user that can't be found in the existing list of games
        all_titles (list): list of every games title
        input_box (tk.Text): Text input box from the GUI
        line (int): line number of the current text in the input text box
    
    Returns:
        str: title of the corrected game
    """

    # Finds the 5 closest matching titles to the bad title
    matches = difflib.get_close_matches(bad_title, all_titles, n=5, cutoff=0.5)
    selected = tk.StringVar(value="")

    # If no matches
    if not matches:
        return None

    # GUI element for suggested title corrections
    popup = tk.Toplevel(root)
    popup.title("Did you mean...")
    popup.geometry("300x200")
    popup.grab_set()
    tk.Label(popup, text=f"Title '{bad_title}' not found.\nDid you mean:").pack(pady=10)


    # Function called when a suggestion button is clicked
    def choose(match):
        selected.set(match)
        popup.destroy()
        
        # Calculate the line index in input (Tkinter is 1-based for lines)
        line_number = line + 1
        line_start = f"{line_number}.0"
        line_end = f"{line_number}.end"

        # Get the specific line content
        line_text = input_box.get(line_start, line_end)

        # Replace the bad title with the selected match in that line only
        updated_line = line_text.replace(bad_title, match)

        # Replace just that line in the text widget
        input_box.delete(line_start, line_end)
        input_box.insert(line_start, updated_line)
            
    # Button for each of the suggested corrections
    for match in matches:
        tk.Button(popup, text=match, command=lambda m=match: choose(m)).pack(fill="x", padx=20, pady=2)

    # Button for no similar matches
    tk.Button(popup, text="None of these", command=popup.destroy).pack(pady=10)

    popup.wait_window()
    return selected.get() if selected.get() else None

def choose_franchises_to_exclude(root, input_games, dataset):
    """
    Get the list of franchises from the user inputted games,
    and the asks the user which ones to exclude via the GUI 

    Args:
        root (tk): GUI root of the program
        input_games (list): A list of the users inputted games
        dataset (DataFrame): Dataframe of the games information
    
    Returns:
        list: list of franchises to exclude
    """
    franchises = set()
    # Gets the index for each given title
    title_to_index = {t: i for i, t in enumerate(dataset["Title"])}
    # Loop through each inputted game
    for title in input_games:
        # If the game is found, get the franchises
        if title in title_to_index:
            idx = title_to_index[title]
            franchise_field= dataset.loc[idx, "Franchise"]
            # If franchises are found, split them
            if franchise_field:
                for f in franchise_field.split():
                    if f:
                        franchises.add(f)
    if not franchises:
        return []

    # Create GUI box for exluded franchises
    popup = tk.Toplevel(root)
    popup.title("Exclude Franchises")
    popup.geometry("300x200")
    popup.grab_set()
    tk.Label(popup, text="Select franchises to exclude:").pack(pady=5)

    vars_dict = {}
    # Create a checkbox for each franchise 
    for f in sorted(franchises):
        var = tk.BooleanVar(value=True)
        cb = tk.Checkbutton(popup, text=f, variable=var)
        cb.pack(anchor="w")
        vars_dict[f] = var

    result = []

    # Collect franchises the user wants to exclude
    def confirm():
        for f, var in vars_dict.items():
            if var.get():
                result.append(f)
        popup.destroy()

    # Confirm button
    tk.Button(popup, text="Confirm", command=confirm).pack(pady=10)
    popup.wait_window()
    return result