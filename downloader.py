import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
import time
import getpass

class DanCarlinDownloader:
    def __init__(self, output_dir='dan_carlin_episodes'):
        self.output_dir = output_dir
        self.session = requests.Session()
        self.base_url = 'https://www.dancarlin.com'
        self.login_url = f'{self.base_url}/wp-login.php'
        self.downloads_url = f'{self.base_url}/my-account/downloads/'
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def login(self, username, password):
        """Log in to Dan Carlin's website"""
        print("Logging in...")
        
        # Get login page first to capture any necessary cookies/tokens
        login_page = self.session.get(self.login_url)
        soup = BeautifulSoup(login_page.text, 'html.parser')
        
        # Find login form fields (may need adjusting based on actual form structure)
        login_data = {
            'log': username,
            'pwd': password,
            'wp-submit': 'Log In',
            'redirect_to': self.downloads_url,
            'testcookie': '1'
        }
        
        # Look for any hidden form fields that might be needed
        for hidden in soup.find_all('input', type='hidden'):
            login_data[hidden.get('name')] = hidden.get('value')
        
        # Attempt login
        response = self.session.post(self.login_url, data=login_data)
        
        if 'my-account' in response.url:
            print("Login successful!")
            return True
        else:
            print("Login failed. Please check your credentials.")
            return False

    def get_download_links(self):
        """Extract all download links from the downloads page"""
        print("Fetching download links...")

        response = self.session.get(self.downloads_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the downloads table
        download_table = soup.find('table', class_='woocommerce-table--order-downloads')
        if not download_table:
            print("Could not find downloads table. Are you logged in?")
            return []

        # Find all download links and their corresponding titles
        download_links = []
        for row in download_table.find_all('tr'):
            # Skip header row
            if row.find('th'):
                continue

            title_cell = row.find('td', class_='download-product')
            download_cell = row.find('td', class_='download-file')

            if title_cell and download_cell:
                title = title_cell.get_text().strip()
                download_link = download_cell.find('a', class_='woocommerce-MyAccount-downloads-file')

                if download_link and download_link.get('href'):
                    download_links.append({
                        'title': title,
                        'url': download_link['href']
                    })
                    print(f"Found: {title}")

        print(f"\nFound {len(download_links)} episodes")
        return download_links  # Return full dict with both URL and title

    def download_all(self, max_concurrent=3):
        """Download all episodes"""
        episodes = self.get_download_links()

        if not episodes:
            print("No download links found. Please check if you're properly logged in.")
            return

        print(f"\nStarting download of {len(episodes)} episodes...")

        def download_with_title(episode):
            print(f"\nStarting download: {episode['title']}")
            self.download_episode(episode['url'])

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            executor.map(download_with_title, episodes)

    def download_episode(self, url):
        """Download a single episode"""
        try:
            # First make a GET request (not HEAD) to follow all redirects to the final URL
            response = self.session.get(url, stream=True)
            response.raise_for_status()

            # Try to get filename from content-disposition header
            filename = None
            if 'content-disposition' in response.headers:
                content_disp = response.headers['content-disposition']
                if 'filename=' in content_disp:
                    filename = content_disp.split('filename=')[-1].strip('"').strip("'")

            # If no filename from header, use the title from the URL or generate one
            if not filename or filename == '':
                # Try to extract episode number and name from the final URL
                final_path = urlparse(response.url).path
                if final_path:
                    filename = os.path.basename(final_path)

                # If still no good filename, use a sanitized version of the title
                if not filename or filename == '' or filename == 'download':
                    # At this point we need to generate a filename
                    filename = url.split('download_file=')[-1].split('&')[0]
                    filename = f"dan_carlin_episode_{filename}.mp3"

            # Clean up filename and ensure .mp3 extension
            filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.'))
            if not filename.endswith('.mp3'):
                filename += '.mp3'

            filepath = os.path.join(self.output_dir, filename)

            # Check if file already exists
            if os.path.exists(filepath):
                print(f"Skipping {filename} - already exists")
                return

            # Get total size for progress tracking
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            start_time = time.time()

            print(f"Downloading: {filename}")
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Calculate progress
                        if total_size > 0:  # Avoid division by zero
                            progress = (downloaded / total_size) * 100
                            elapsed_time = time.time() - start_time
                            speed = downloaded / (1024 * 1024 * elapsed_time) if elapsed_time > 0 else 0
                            print(f"\r{filename}: {progress:.1f}% ({speed:.1f} MB/s)", end="")

            print(f"\nCompleted: {filename}")

        except requests.exceptions.RequestException as e:
            print(f"Error downloading: {e}")


def main():
    downloader = DanCarlinDownloader()
    
    # Credentials
    username = "***"
    password = "***"
    
    # Login and start download
    if downloader.login(username, password):
        downloader.download_all()

if __name__ == "__main__":
    main()
