#!/usr/bin/env python3
"""
Goodreads Profile Scraper

This script scrapes a public Goodreads profile to extract all read books
with their authors and publish dates.

Usage:
    python goodreads_scraper.py <goodreads_username>
    
Example:
    python goodreads_scraper.py johndoe
"""

import requests
from bs4 import BeautifulSoup
import sys
import time
import csv
from typing import List, Dict, Optional
import re
from urllib.parse import urljoin


class GoodreadsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.base_url = "https://www.goodreads.com"
        
    def get_profile_url(self, username: str) -> str:
        """Generate the profile URL for a given username."""
        return f"{self.base_url}/user/show/{username}"
    
    def get_books_url(self, username: str) -> str:
        """Generate the books URL for a given username."""
        return f"{self.base_url}/user/show/{username}/books"
    
    def get_read_books_url(self, username: str, page: int = 1) -> str:
        """Generate the read books URL for a given username and page."""
        return f"{self.base_url}/review/list/{username}?shelf=read&page={page}"
    
    def get_currently_reading_url(self, username: str, page: int = 1) -> str:
        """Generate the currently reading books URL for a given username and page."""
        return f"{self.base_url}/review/list/{username}?shelf=currently-reading&page={page}"
    
    def scrape_profile(self, username: str) -> Dict:
        """Scrape basic profile information."""
        profile_url = self.get_profile_url(username)
        
        try:
            response = self.session.get(profile_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract profile information
            profile_info = {}
            
            # Get display name
            name_elem = soup.find('h1', class_='userProfileName')
            if name_elem:
                profile_info['display_name'] = name_elem.get_text(strip=True)
            
            # Get location
            location_elem = soup.find('span', class_='userLocation')
            if location_elem:
                profile_info['location'] = location_elem.get_text(strip=True)
            
            # Get join date
            join_elem = soup.find('span', string=re.compile(r'Member since'))
            if join_elem:
                join_text = join_elem.get_text(strip=True)
                profile_info['member_since'] = join_text.replace('Member since', '').strip()
            
            return profile_info
            
        except requests.RequestException as e:
            print(f"Error scraping profile: {e}")
            return {}
    
    def scrape_read_books(self, username: str, max_pages: int = 50) -> List[Dict]:
        """Scrape all read books from the user's profile."""
        books = []
        page = 1
        
        print(f"Scraping read books for user: {username}")
        
        while page <= max_pages:
            print(f"Scraping page {page}...")
            
            try:
                books_url = self.get_read_books_url(username, page)
                response = self.session.get(books_url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Debug: Save HTML for inspection
                if page == 1:
                    with open(f"debug_page_{username}.html", "w", encoding="utf-8") as f:
                        f.write(str(soup.prettify()))
                    print(f"Saved debug HTML to debug_page_{username}.html")
                
                # Try multiple selectors for book entries
                book_entries = []
                
                # Method 1: Look for table rows with class 'bookalike'
                book_entries = soup.find_all('tr', class_='bookalike')
                
                # Method 2: If no books found, try looking for any table rows that might contain books
                if not book_entries:
                    print("No 'bookalike' rows found, trying alternative selectors...")
                    # Look for any table rows that contain book-like information
                    all_rows = soup.find_all('tr')
                    for row in all_rows:
                        # Check if row contains book title links
                        if row.find('a', href=re.compile(r'/book/show/')):
                            book_entries.append(row)
                
                # Method 3: Look for div elements that might contain books
                if not book_entries:
                    print("No table rows found, trying div-based layout...")
                    # Look for divs that might contain book information
                    book_divs = soup.find_all('div', class_=re.compile(r'book|item|entry'))
                    for div in book_divs:
                        if div.find('a', href=re.compile(r'/book/show/')):
                            book_entries.append(div)
                
                print(f"Found {len(book_entries)} potential book entries")
                
                if not book_entries:
                    print(f"No book entries found on page {page}")
                    # Debug: Show what we did find
                    print("Debug: Looking for any links to books...")
                    book_links = soup.find_all('a', href=re.compile(r'/book/show/'))
                    print(f"Found {len(book_links)} book links on page")
                    if book_links:
                        print("First few book links:")
                        for i, link in enumerate(book_links[:3]):
                            print(f"  {i+1}. {link.get('href')} - {link.get_text(strip=True)}")
                    break
                
                page_books = []
                for entry in book_entries:
                    book_info = self._extract_book_info(entry)
                    if book_info:
                        # Add a flag to indicate this is from read shelf
                        book_info['shelf'] = 'read'
                        page_books.append(book_info)
                
                if not page_books:
                    print(f"No books extracted from page {page}")
                    # Debug: Show what the first entry looks like
                    if book_entries:
                        print("Debug: First entry HTML structure:")
                        print(book_entries[0].prettify()[:500])
                    break
                
                books.extend(page_books)
                print(f"Found {len(page_books)} books on page {page}")
                
                # Check if there's a next page
                next_link = soup.find('a', class_='next_page')
                if not next_link:
                    print("No next page found")
                    break
                
                page += 1
                
                # Be respectful with requests
                time.sleep(1)
                
            except requests.RequestException as e:
                print(f"Error scraping page {page}: {e}")
                break
        
        print(f"Total books scraped: {len(books)}")
        return books
    
    def scrape_currently_reading(self, username: str, max_pages: int = 10) -> List[Dict]:
        """Scrape all currently reading books from the user's profile."""
        books = []
        page = 1
        
        print(f"Scraping currently reading books for user: {username}")
        
        while page <= max_pages:
            print(f"Scraping currently reading page {page}...")
            
            try:
                books_url = self.get_currently_reading_url(username, page)
                response = self.session.get(books_url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Debug: Save HTML for inspection
                if page == 1:
                    with open(f"debug_currently_reading_{username}.html", "w", encoding="utf-8") as f:
                        f.write(str(soup.prettify()))
                    print(f"Saved debug HTML to debug_currently_reading_{username}.html")
                
                # Try multiple selectors for book entries
                book_entries = []
                
                # Method 1: Look for table rows with class 'bookalike'
                book_entries = soup.find_all('tr', class_='bookalike')
                
                # Method 2: If no books found, try looking for any table rows that might contain books
                if not book_entries:
                    print("No 'bookalike' rows found, trying alternative selectors...")
                    # Look for any table rows that contain book-like information
                    all_rows = soup.find_all('tr')
                    for row in all_rows:
                        # Check if row contains book title links
                        if row.find('a', href=re.compile(r'/book/show/')):
                            book_entries.append(row)
                
                # Method 3: Look for div elements that might contain books
                if not book_entries:
                    print("No table rows found, trying div-based layout...")
                    # Look for divs that might contain book information
                    book_divs = soup.find_all('div', class_=re.compile(r'book|item|entry'))
                    for div in book_divs:
                        if div.find('a', href=re.compile(r'/book/show/')):
                            book_entries.append(div)
                
                print(f"Found {len(book_entries)} potential currently reading book entries")
                
                if not book_entries:
                    print(f"No currently reading book entries found on page {page}")
                    # Debug: Show what we did find
                    print("Debug: Looking for any links to books...")
                    book_links = soup.find_all('a', href=re.compile(r'/book/show/'))
                    print(f"Found {len(book_links)} book links on page")
                    if book_links:
                        print("First few book links:")
                        for i, link in enumerate(book_links[:3]):
                            print(f"  {i+1}. {link.get('href')} - {link.get_text(strip=True)}")
                    break
                
                page_books = []
                for entry in book_entries:
                    book_info = self._extract_book_info(entry)
                    if book_info:
                        # Add a flag to indicate this is currently reading
                        book_info['shelf'] = 'currently-reading'
                        page_books.append(book_info)
                
                if not page_books:
                    print(f"No currently reading books extracted from page {page}")
                    # Debug: Show what the first entry looks like
                    if book_entries:
                        print("Debug: First entry HTML structure:")
                        print(book_entries[0].prettify()[:500])
                    break
                
                books.extend(page_books)
                print(f"Found {len(page_books)} currently reading books on page {page}")
                
                # Check if there's a next page
                next_link = soup.find('a', class_='next_page')
                if not next_link:
                    print("No next page found")
                    break
                
                page += 1
                
                # Be respectful with requests
                time.sleep(1)
                
            except requests.RequestException as e:
                print(f"Error scraping currently reading page {page}: {e}")
                break
        
        print(f"Total currently reading books scraped: {len(books)}")
        return books
    
    def _extract_book_info(self, book_entry) -> Optional[Dict]:
        """Extract book information from a book entry."""
        try:
            book_info = {}
            
            # Get book title - look for the title field
            title_elem = book_entry.find('td', class_='field title')
            if title_elem:
                title_link = title_elem.find('a')
                if title_link:
                    book_info['title'] = title_link.get_text(strip=True)
                    book_info['book_url'] = urljoin(self.base_url, title_link.get('href', ''))
            
            # Get author - look for the author field
            author_elem = book_entry.find('td', class_='field author')
            if author_elem:
                author_link = author_elem.find('a')
                if author_link:
                    book_info['author'] = author_link.get_text(strip=True)
                    book_info['author_url'] = urljoin(self.base_url, author_link.get('href', ''))
            
            # Get ISBN - look for the isbn field
            isbn_elem = book_entry.find('td', class_='field isbn')
            if isbn_elem:
                isbn_value = isbn_elem.find('div', class_='value')
                if isbn_value:
                    isbn_text = isbn_value.get_text(strip=True)
                    if isbn_text and isbn_text != 'None':
                        book_info['isbn'] = isbn_text
            
            # Get publish date - look for the date_pub field
            pub_date_elem = book_entry.find('td', class_='field date_pub')
            if pub_date_elem:
                pub_date_value = pub_date_elem.find('div', class_='value')
                if pub_date_value:
                    pub_date_text = pub_date_value.get_text(strip=True)
                    if pub_date_text and pub_date_text != 'None':
                        # Extract year from date like "Mar 26, 1920"
                        year_match = re.search(r'(\d{4})', pub_date_text)
                        if year_match:
                            book_info['publish_date'] = year_match.group(1)
                        else:
                            book_info['publish_date'] = pub_date_text
            
            # Get rating - look for the rating field
            rating_elem = book_entry.find('td', class_='field rating')
            if rating_elem:
                rating_value = rating_elem.find('div', class_='value')
                if rating_value:
                    # Look for static stars to determine rating
                    static_stars = rating_value.find_all('span', class_='staticStar')
                    if static_stars:
                        filled_stars = sum(1 for star in static_stars if 'p10' in star.get('class', []))
                        if filled_stars > 0:
                            book_info['rating'] = filled_stars
            
            # Get average rating - look for the avg_rating field
            avg_rating_elem = book_entry.find('td', class_='field avg_rating')
            if avg_rating_elem:
                avg_rating_value = avg_rating_elem.find('div', class_='value')
                if avg_rating_value:
                    avg_rating_text = avg_rating_value.get_text(strip=True)
                    if avg_rating_text and avg_rating_text != 'None':
                        try:
                            book_info['avg_rating'] = float(avg_rating_text)
                        except ValueError:
                            pass
            
            # Get number of pages - look for the num_pages field
            pages_elem = book_entry.find('td', class_='field num_pages')
            if pages_elem:
                pages_value = pages_elem.find('div', class_='value')
                if pages_value:
                    pages_text = pages_value.get_text(strip=True)
                    if pages_text and pages_text != 'None':
                        # Extract just the number
                        pages_match = re.search(r'(\d+)', pages_text)
                        if pages_match:
                            book_info['pages'] = int(pages_match.group(1))
            
            # Get date read - this might be in a different field or not available
            # For now, we'll skip this as it's not visible in the current structure
            
            return book_info if book_info.get('title') else None
            
        except Exception as e:
            print(f"Error extracting book info: {e}")
            return None
    
    def save_to_csv(self, books: List[Dict], filename: str = 'goodreads_books.csv'):
        """Save books to a CSV file."""
        if not books:
            print("No books to save")
            return
        
        fieldnames = ['title', 'author', 'publish_date', 'isbn', 'rating', 'avg_rating', 'pages', 'book_url', 'author_url', 'shelf']
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for book in books:
                    # Ensure all fields are present
                    row = {field: book.get(field, '') for field in fieldnames}
                    writer.writerow(row)
            
            print(f"Books saved to {filename}")
            
        except Exception as e:
            print(f"Error saving to CSV: {e}")
    
    def print_books_summary(self, books: List[Dict]):
        """Print a summary of scraped books."""
        if not books:
            print("No books found")
            return
        
        print(f"\n{'='*80}")
        print(f"BOOKS SUMMARY")
        print(f"{'='*80}")
        print(f"Total books: {len(books)}")
        
        # Count by publish decade
        decades = {}
        for book in books:
            if book.get('publish_date'):
                try:
                    year = int(book['publish_date'])
                    decade = (year // 10) * 10
                    decades[decade] = decades.get(decade, 0) + 1
                except ValueError:
                    continue
        
        if decades:
            print(f"\nBooks by decade:")
            for decade in sorted(decades.keys()):
                print(f"  {decade}s: {decades[decade]} books")
        
        # Top authors
        authors = {}
        for book in books:
            if book.get('author'):
                authors[book['author']] = authors.get(book['author'], 0) + 1
        
        if authors:
            print(f"\nTop authors:")
            sorted_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)[:10]
            for author, count in sorted_authors:
                print(f"  {author}: {count} books")
        
        print(f"\n{'='*80}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python goodreads_scraper.py <goodreads_username>")
        print("Example: python goodreads_scraper.py johndoe")
        sys.exit(1)
    
    username = sys.argv[1]
    scraper = GoodreadsScraper()
    
    print(f"Starting Goodreads scraper for user: {username}")
    print("-" * 50)
    
    # Scrape profile info
    profile_info = scraper.scrape_profile(username)
    if profile_info:
        print("Profile information:")
        for key, value in profile_info.items():
            print(f"  {key}: {value}")
        print()
    
    # Scrape read books
    read_books = scraper.scrape_read_books(username)
    
    # Scrape currently reading books
    currently_reading_books = scraper.scrape_currently_reading(username)
    
    # Combine all books
    all_books = read_books + currently_reading_books
    
    if all_books:
        # Print summary for read books
        if read_books:
            print(f"\n{'='*80}")
            print(f"READ BOOKS SUMMARY")
            print(f"{'='*80}")
            scraper.print_books_summary(read_books)
        
        # Print summary for currently reading books
        if currently_reading_books:
            print(f"\n{'='*80}")
            print(f"CURRENTLY READING SUMMARY")
            print(f"{'='*80}")
            print(f"Total currently reading books: {len(currently_reading_books)}")
            print(f"\nCurrently reading books:")
            for i, book in enumerate(currently_reading_books, 1):
                print(f"{i}. {book.get('title', 'Unknown')} by {book.get('author', 'Unknown')}")
                if book.get('publish_date'):
                    print(f"   Published: {book['publish_date']}")
                if book.get('rating'):
                    print(f"   Rating: {book['rating']}")
                print()
        
        # Save to CSV
        filename = f"{username}_goodreads_books.csv"
        scraper.save_to_csv(all_books, filename)
        
        # Print combined summary
        print(f"\n{'='*80}")
        print(f"COMBINED SUMMARY")
        print(f"{'='*80}")
        print(f"Total books: {len(all_books)} ({len(read_books)} read, {len(currently_reading_books)} currently reading)")
        
        # Print first few books as preview
        print(f"\nFirst 5 books preview:")
        print("-" * 50)
        for i, book in enumerate(all_books[:5], 1):
            shelf_info = f" [{book.get('shelf', 'read')}]" if book.get('shelf') else ""
            print(f"{i}. {book.get('title', 'Unknown')} by {book.get('author', 'Unknown')}{shelf_info}")
            if book.get('publish_date'):
                print(f"   Published: {book['publish_date']}")
            if book.get('rating'):
                print(f"   Rating: {book['rating']}")
            print()
        
        if len(all_books) > 5:
            print(f"... and {len(all_books) - 5} more books")
    
    else:
        print("No books found. Please check:")
        print("1. The username is correct")
        print("2. The profile is public")
        print("3. The user has marked books as read or currently reading")
        print("\nDebug information has been saved to debug_page_{username}.html")


if __name__ == "__main__":
    main()
