import configparser
import json
import os
import requests
import sys
import imaplib 

if sys.platform == 'win32':
    print("Autocomplete is not supported on Windows Native CommandPrompt (Try WSL instead)")
else:
    import readline

class Alias:
    def __init__(self, email, folder=None, labels=None):
        self.email = email
        self.folder = folder
        self.labels = labels if labels is not None else []

    def assign_folder(self, folder):
        self.folder = folder

    def add_label(self, label):
        if label not in self.labels:
            self.labels.append(label)

    def to_dict(self):
        return {'email': self.email, 'folder': self.folder, 'labels': self.labels}
    
    def clear_folder(self):
        self.folder = None

    def clear_labels(self):
        self.labels = []

    @staticmethod
    def from_dict(data):
        return Alias(data['email'], data['folder'], data['labels'])


def get_all_aliases(api_key, pinned=None, disabled=None, enabled=None):
    all_aliases = []
    page_id = 0

    while True:
        print(f"Getting Aliases Page {page_id}")
        url = f'https://api.simplelogin.io/api/v2/aliases?page_id={page_id}'

        # Add optional parameters to the query
        if pinned is not None:
            url += f'&pinned={str(pinned).lower()}'
        if disabled is not None:
            url += f'&disabled={str(disabled).lower()}'
        if enabled is not None:
            url += f'&enabled={str(enabled).lower()}'

        headers = {'Authentication': api_key}
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            raise Exception("Failed to fetch aliases: " + response.text)

        data = response.json()
        aliases = data['aliases']
        if not aliases:
            break  # Exit loop if no more aliases
        all_aliases.extend(aliases)
        page_id += 1


    return all_aliases

def load_aliases_from_json(filename):
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
            return {alias['email']: Alias.from_dict(alias) for alias in data}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        print("Error: JSON file is malformed.")
        return {}
    
def save_aliases_to_json(aliases, filename):
    with open(filename, 'w') as file:
        json.dump([alias.to_dict() for alias in aliases.values()], file, indent=4)


def completer(text, state):
    options = [i for i in current_completions if i.startswith(text)]
    if state < len(options):
        return options[state]
    else:
        return None

def get_imap_folders(host, port, username, password):
    try:
        # Connect to the IMAP server
        imap = imaplib.IMAP4(host, port)

        # Start TLS for security
        imap.starttls()

        # Login to the server
        imap.login(username, password)

        # Get the list of folders
        status, folders_raw = imap.list()

        # Close the connection
        imap.logout()

        # Extract folder names if the operation was successful
        folder_names = []
        if status == 'OK':
            for folder in folders_raw:
                folder_names.append(folder.decode().split(' "/" ')[1])

        folders = []
        labels = []
        for folder in folder_names:
            folder = folder.strip('\"')
            length = len(folder.split("/"))
            if folder.split("/")[0] == "Folders":
                if length > 1:
                    if length > 2:
                        folders.append(".".join(folder.split("/")[1:]))
                    else:
                        folders.append(folder.split("/")[1])
            elif folder.split("/")[0] == "Labels":
                if length > 1:
                    labels.append(folder.split("/")[1])

        return folders, labels
    except Exception as e:
        print(f"An error occurred: {e}")
        return [],[]
    
    
def create_folder(host, port, username, password, folder_name):
    try:
        # Connect to the IMAP server
        imap = imaplib.IMAP4(host, port)

        # Start TLS for security
        imap.starttls()

        # Login to the server
        imap.login(username, password)
        
        # Create a new folder
        status, response = imap.create(folder_name)
        if status == 'OK':
            print(f"Folder '{folder_name}' created successfully.")
        else:
            print(f"Failed to create folder: {response}")
        # Logout
        imap.logout()
    except imaplib.IMAP4.error as e:
        print(f"IMAP error: {e}")
    except Exception as e:
        print(f"Error: {e}")    
    

def setup_config():
    config = configparser.ConfigParser()
    config_file = 'config.ini'
    config_changed = False

    if not os.path.exists(config_file):
        config['simplelogin'] = {'api_key': ''}
        config['mail'] = {'folders': json.dumps([]), 'labels': json.dumps([]), 'host': '', 'port': '', 'username': '', 'password': ''}
        config_changed = True
    else:
        config.read(config_file)
        if 'simplelogin' not in config:
            config['simplelogin'] = {'api_key': ''}
            config_changed = True
        if 'mail' not in config:
            config['mail'] = {'folders': json.dumps([]), 'labels': json.dumps([]), 'host': '', 'port': '', 'username': '', 'password': ''}
            config_changed = True

    # Check and update API key if needed
    if not config['simplelogin']['api_key']:
        api_key = input("Enter your SimpleLogin API key: ").strip()
        config['simplelogin']['api_key'] = api_key
        config_changed = True

    if not config['mail']['host']:
        host = input("Enter IMAP HOST IP Address: ").strip()
        config['mail']['host'] = host
        config_changed = True

    if not config['mail']['port']:
        port = input("Enter Port: ").strip()
        config['mail']['port'] = port
        config_changed = True
        
    if not config['mail']['username']:
        username = input("Enter Username: ").strip()
        config['mail']['username'] = username
        config_changed = True

    if not config['mail']['password']:
        password = input("Enter Password: ").strip()
        config['mail']['password'] = password
        config_changed = True


    if config_changed:
        with open(config_file, 'w') as file:
            config.write(file)
        print(f"Config file updated/created at {config_file}")

    return config

def get_user_folder_assignments(aliases, folders, new_folders, labels, new_labels, filename, config):
    # Load existing assignments
    existing_aliases = load_aliases_from_json(filename)
    # new_folders = []  # List to keep track of newly added folders
    # new_labels = []   # List to keep track of newly added labels    

    # Set up autocomplete for folders and labels
    global current_completions
    # commands = folders + labels
    if sys.platform != 'win32':
        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")


    # Merge with new aliases
    if aliases:
        for alias in aliases:
            if alias not in existing_aliases:
                existing_aliases[alias] = Alias(alias)


    # User input for folder assignments
    # for alias, alias_obj in existing_aliases.items():
    for alias in existing_aliases:
        alias_obj = existing_aliases.get(alias, Alias(alias))
        print(f"Assigning folder and labels for alias: {alias}")

        # Check if alias already has assignments
        has_assignments = alias_obj.folder or alias_obj.labels
        if has_assignments:
            print(f"Current folder: {alias_obj.folder or 'None'}")
            print(f"Current labels: {', '.join(alias_obj.labels) if alias_obj.labels else 'None'}")
            edit = input("Do you want to edit this alias? (y/n, 'exit' to finish): ").strip().lower()
            if edit == 'exit':
                break
            elif edit == 'y':
                alias_obj.clear_folder()  # Clear existing folder
                alias_obj.clear_labels()  # Clear existing labels
            else:
                continue
               
        current_completions = folders
        if sys.platform != 'win32':
            folder_input = input(f"Enter folder name for {alias} (Tab to autocomplete, leave blank if none and type 'exit' to leave): ")
        else:
            folder_input = input(f"Enter folder name for {alias} (leave blank if none and type 'exit' to leave): ")

        if folder_input:
            if folder_input == "exit":
                break
            elif folder_input not in folders:
                folders.append(folder_input)
                new_folders.append(folder_input)
            alias_obj.assign_folder(folder_input)

        current_completions = labels
        while True:
            if sys.platform != 'win32':
                label_input = input(f"Enter label for {alias} (Tab to autocomplete, type 'done' to finish): ")
            else:
                label_input = input(f"Enter label for {alias} (type 'done' to finish): ")
            if label_input.lower() == 'done':
                break
            if label_input:
                if label_input not in labels:
                    labels.append(label_input)
                    new_labels.append(label_input)
                alias_obj.add_label(label_input)

        
        # Update folders and labels in config and save it
        config['mail']['folders'] = json.dumps(folders)
        config['mail']['labels'] = json.dumps(labels)
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

    # Save updated assignments
    save_aliases_to_json(existing_aliases, filename)

    return existing_aliases, new_folders, new_labels

def generate_sieve_script(aliases):
    sieve_script = """require ["include", "environment", "variables", "relational", "comparator-i;ascii-numeric", "spamtest", "fileinto", "imap4flags"];

# Generated: Do not run this script on spam messages
if allof (environment :matches "vnd.proton.spam-threshold" "*",
spamtest :value "ge" :comparator "i;ascii-numeric" "${1}")
{
    return;
}

"""

    for email, alias_obj in aliases.items():
        if alias_obj.folder or alias_obj.labels:
            sieve_script += f'if header :is "X-Simplelogin-Envelope-To" "{email}"{{\n'
            if alias_obj.folder:
                sieve_script += f'    fileinto "{alias_obj.folder}";\n'
            for label in alias_obj.labels:
                sieve_script += f'    fileinto "{label}";\n'
            sieve_script += '    stop;\n}\n\n'

    return sieve_script


def save_sieve_script_to_file(sieve_script, filename="sieve_script.sieve"):
    with open(filename, "w") as file:
        file.write(sieve_script)
    print(f"Sieve script saved to {filename}")


def main():
    config = setup_config()
    new_folders = []
    new_labels = []
    aliases = None
    filename = "aliases.json"

    update_aliases = input("Do you want to update the aliases from SimpleLogin? (y/n): ").strip().lower() == 'y'
    if update_aliases:
        # Authenticate and fetch data
        api_key = config.get("simplelogin", "api_key")
        alias_dicts = get_all_aliases(api_key)
        aliases = [alias_dict['email'] for alias_dict in alias_dicts]  # Extracting email addresses
   
    do_assignments = input("Do you want to perform folder and label assignments? (y/n): ").strip().lower() == 'y'
    if do_assignments:
        if not os.path.exists(filename) and aliases == None:
            print("No Aliases can be loaded from file, and no Aliases were loaded from SimpleLogin")
            quit()
        folders, labels = get_imap_folders(config.get("mail","host"),config.get("mail","port"),config.get("mail","username"),config.get("mail","password"))

        foldersLocal = json.loads(config.get('mail', "folders", fallback="[]"))
        labelsLocal = json.loads(config.get('mail', 'labels', fallback="[]"))
        for f in foldersLocal:
            if f not in folders:
                folders.append(f)
                new_folders.append(f)
        for l in labelsLocal:
            if l not in labels:
                labels.append(l)
                new_labels.append(l)
        assignments, new_folders, new_labels = get_user_folder_assignments(aliases, folders, new_folders, labels, new_labels, filename, config)
    else:
        if not os.path.exists(filename):
            
            quit()        
        assignments = load_aliases_from_json(filename)
        

    # Generate Sieve script
    sieve_script = generate_sieve_script(assignments)
    save_sieve_script_to_file(sieve_script)

    # Print the new folders and labels created during this session
    if new_folders:
        for nFolder in new_folders:
            if "." in nFolder:
                nFolder.replace(".","/")
            fnFolder = f"Folders/{nFolder}"
            create_folder(config.get("mail","host"),config.get("mail","port"),config.get("mail","username"),config.get("mail","password"), fnFolder)
        print("\nNew folders created:")
        print("\n".join(new_folders))
    if new_labels:
        for nLabel in new_labels:
            fnLabel = f"Labels/{nLabel}"
            create_folder(config.get("mail","host"),config.get("mail","port"),config.get("mail","username"),config.get("mail","password"), fnLabel)
        print("\nNew labels created:")
        print("\n".join(new_labels))


    

if __name__ == "__main__":
    main()
