# This script reads an input file (e.g., input.txt) where each line
# contains text separated by a tilde (~).
# It takes the second part of the text to construct a URL and saves
# the results to an output file.

import os

def generate_remilia_urls(input_file='input.txt', output_file='output_urls.txt'):
    """
    Reads usernames from an input file, formats them into URLs,
    and writes them to an output file.

    Args:
        input_file (str): The name of the file to read data from.
        output_file (str): The name of the file to save the generated URLs to.
    """
    # Get the directory of the script to create files in the same location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, input_file)
    output_path = os.path.join(script_dir, output_file)

    try:
        # Open the input and output files with UTF-8 encoding to prevent errors
        with open(input_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
            print(f"Reading data from: {input_path}")
            
            # Process each line in the input file
            for line in infile:
                # Remove any leading/trailing whitespace
                clean_line = line.strip()
                
                # Ensure the line is not empty and contains the separator
                if '~' in clean_line:
                    # Split the line at the tilde and get the second part
                    try:
                        username = clean_line.split('~')[1]
                        
                        # Construct the URL
                        url = f"https://remilia.com/~{username}"
                        
                        # Print the URL to the console for immediate feedback
                        print(url)
                        
                        # Write the URL to the output file, followed by a newline
                        outfile.write(url + '\n')
                    except IndexError:
                        print(f"Warning: Skipping malformed line -> {clean_line}")

        print(f"\nSuccessfully generated URLs and saved them to: {output_path}")

    except FileNotFoundError:
        print(f"Error: The input file '{input_path}' was not found.")
        print("Please make sure 'input.txt' is in the same folder as the script.")
    except UnicodeDecodeError:
        print(f"Error: A character encoding error occurred while reading {input_file}.")
        print("Please ensure the file is saved with UTF-8 encoding.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# Run the function when the script is executed
if __name__ == "__main__":
    generate_remilia_urls()

