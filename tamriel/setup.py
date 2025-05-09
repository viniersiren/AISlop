import subprocess
import sys
import os

def get_package_size(package_name):
    """Get the size of a package using pip."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            capture_output=True,
            text=True
        )
        for line in result.stdout.split('\n'):
            if line.startswith('Size:'):
                return line.split(': ')[1].strip()
        return "Unknown"
    except:
        return "Unknown"

def main():
    print("Elder Scrolls Lore Video Generator Setup")
    print("=======================================")
    print("\nRequired packages and their sizes:")
    print("----------------------------------")
    
    # Read requirements
    with open('requirements.txt', 'r') as f:
        requirements = f.readlines()
    
    total_size = 0
    packages = []
    
    for req in requirements:
        if req.strip() and not req.startswith('#'):
            package = req.split('==')[0].strip()
            size = get_package_size(package)
            packages.append((package, size))
            print(f"{package}: {size}")
            if size != "Unknown":
                try:
                    total_size += float(size.split()[0])
                except:
                    pass
    
    print(f"\nTotal estimated size: {total_size:.1f} MB")
    
    # Ask for confirmation
    response = input("\nDo you want to install these packages? (y/n): ").lower()
    if response == 'y':
        print("\nInstalling packages...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("\nInstallation complete!")
        
        # Check for Raleway font
        if not os.path.exists("Raleway-Bold.ttf"):
            print("\nWarning: Raleway-Bold.ttf font file not found!")
            print("Please download the Raleway font and place Raleway-Bold.ttf in the tamriel folder.")
            print("You can download it from: https://fonts.google.com/specimen/Raleway")
    else:
        print("\nInstallation cancelled.")

if __name__ == "__main__":
    main() 