import tkinter as tk
from tkinter import messagebox
from recommender import rec_engine
from recommender import prepare_dataset, choose_franchises_to_exclude, suggest_title_correction

def get_recommendations():
    """
    Retrieves user input from the GUI, generates game recommendations,
    and then displays them in the output.
    """
    try:
        # Get the input games, one per line
        input_games = input_box.get("1.0", tk.END).strip().splitlines()
        dataset = prepare_dataset()
        # Parses the users and tries to correct them if wrong
        corrected_titles = correct_titles(input_games, root, dataset, input_box)
        if not corrected_titles:
            messagebox.showinfo("No valid games", "No valid game titles were provided.")
            return
        # Ask user what franchises to exclude from given games
        excluded = choose_franchises_to_exclude(root, corrected_titles, dataset)
        # Generate recommendations using the recommender logic
        recommendations = rec_engine(corrected_titles, excluded_franchises=excluded)
        # Clear previous output before showing results
        output_box.delete("1.0", tk.END)
        # Prints the recommended games
        for game in recommendations:
            output_box.insert(tk.END, f"- {game}\n")
    # Prevents errors when the GUI is closed during execution
    except tk.TclError:
        pass

def correct_titles(input_games, root, dataset, input_box):
    """
    Takes the users inputted games and determines whether the title
    is valid or not. If not, sends title to suggestion correction 
    function.

    Args:
        input_games (list): A list of the users inputted games
        root (tk): GUI root of the program
        dataset (DataFrame): Dataframe of the games information
        input_box (tk.Text): Text input box from the GUI

    Returns:
        list: A corrected list of the user's inputted games
    
    """
    corrected = []
    # Get every game's title
    all_titles = dataset["Title"].tolist()
    # Counter for line
    line = 0

    # Loop through the inputted games
    for title in input_games:
        # If title is found then add it
        if title in all_titles:
            corrected.append(title)
        else:
            # If title is not found, then try to suggest corrections
            suggestion = suggest_title_correction(root, title, all_titles, input_box, line)
            # If the user selects a suggested title, add it
            if suggestion:
                corrected.append(suggestion)
                
        line +=1
    return corrected

# Main application window and window title
root = tk.Tk()
root.title("N64 Game Recommender")

# Label
label = tk.Label(root, text="Enter game titles (one per line):")
label.pack()

# Input
input_box = tk.Text(root, height=10, width=50)
input_box.pack()

# Button
recommend_button = tk.Button(root, text="Get Recommendations", command=get_recommendations)
recommend_button.pack()

# Output
output_box = tk.Text(root, height=10, width=50)
output_box.pack()

root.mainloop()