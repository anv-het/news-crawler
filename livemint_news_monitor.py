"""
LiveMint News Monitor - Continuous Financial News Crawler
========================================================

Purpose:
- Continuously monitor LiveMint for new stock market/business news
- Run 24/7 or at scheduled intervals
- Automatically detect and save new articles
- Human-like behavior to avoid detection

Use Cases:
- Feed trading signals/algorithms
- Real-time news analysis
- ML/AI training data
- Custom news dashboard
"""

import asyncio
import json
import random
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
import hashlib

class LiveMintNewsMonitor:
    def __init__(self, config=None):
        self.config = config or {
            'check_interval': 300,  # Check every 5 minutes (300 seconds)
            'sections': [
                'https://www.livemint.com/market',
                'https://www.livemint.com/companies',
                'https://www.livemint.com/money',
            ],
            'output_file': 'livemint_news.json',
            'seen_articles_file': 'seen_articles.json',
            'viewport': {'width': 1536, 'height': 864},
            'headless': True,  # Run in background for 24/7 monitoring
        }
        
        self.seen_articles = self.load_seen_articles()
        self.all_articles = self.load_existing_articles()
    
    def load_seen_articles(self):
        """Load previously seen article IDs to avoid duplicates"""
        seen_file = Path(self.config['seen_articles_file'])
        if seen_file.exists():
            try:
                with open(seen_file, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except:
                return set()
        return set()
    
    def save_seen_articles(self):
        """Save seen article IDs"""
        with open(self.config['seen_articles_file'], 'w', encoding='utf-8') as f:
            json.dump(list(self.seen_articles), f, indent=2)
    
    def load_existing_articles(self):
        """Load existing articles from output file"""
        output_file = Path(self.config['output_file'])
        if output_file.exists():
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_articles(self):
        """Save all articles to output file"""
        with open(self.config['output_file'], 'w', encoding='utf-8') as f:
            json.dump(self.all_articles, f, indent=2, ensure_ascii=False)
    
    def generate_article_id(self, url):
        """Generate unique ID for article based on URL"""
        return hashlib.md5(url.encode()).hexdigest()
    
    async def human_scroll(self, page):
        """Simulate human-like scrolling"""
        scroll_steps = random.randint(2, 4)
        for _ in range(scroll_steps):
            scroll_amount = random.randint(300, 600)
            await page.evaluate(f"window.scrollBy({{ top: {scroll_amount}, behavior: 'smooth' }})")
            await page.wait_for_timeout(random.randint(1000, 2000))
    
    async def scrape_section(self, page, section_url, deep_scrape=False):
        """Scrape articles from a specific LiveMint section
        
        Args:
            page: Playwright page object
            section_url: URL to scrape
            deep_scrape: If True, scroll multiple times to load all available articles
        """
        new_articles = []
        
        try:
            print(f'  📰 Checking: {section_url}')
            await page.goto(section_url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(random.randint(2000, 4000))
            
            # Scroll to load more articles
            if deep_scrape:
                # Deep scrape: scroll more times to load all articles
                print(f'    🔄 Deep scraping (loading all articles)...')
                scroll_count = random.randint(8, 12)  # More scrolls for bulk mode
                for i in range(scroll_count):
                    scroll_amount = random.randint(400, 800)
                    await page.evaluate(f"window.scrollBy({{ top: {scroll_amount}, behavior: 'smooth' }})")
                    await page.wait_for_timeout(random.randint(1500, 3000))
                    
                    # Print progress
                    if (i + 1) % 3 == 0:
                        print(f'    📜 Scroll {i + 1}/{scroll_count}...')
            else:
                # Normal scrape: just scroll a bit
                await self.human_scroll(page)
            
            # Extract articles
            articles = await page.evaluate("""
                () => {
                    const items = [];
                    
                    // LiveMint article selectors (adjust based on actual site structure)
                    const articleElements = document.querySelectorAll('article, .listView, .story, .headline');
                    
                    articleElements.forEach(el => {
                        const titleEl = el.querySelector('h2, h3, .headline, a');
                        const linkEl = el.querySelector('a');
                        const timeEl = el.querySelector('time, .date, .timestamp, span[class*="time"]');
                        const summaryEl = el.querySelector('p, .summary, .excerpt');
                        
                        if (titleEl && linkEl && linkEl.href) {
                            let url = linkEl.href;
                            
                            // Only include actual article URLs
                            if (url.includes('livemint.com') && 
                                !url.includes('#') && 
                                !url.includes('javascript:')) {
                                
                                items.push({
                                    title: titleEl.innerText.trim(),
                                    url: url,
                                    summary: summaryEl ? summaryEl.innerText.trim() : '',
                                    timestamp: timeEl ? timeEl.innerText.trim() : '',
                                    section: window.location.pathname
                                });
                            }
                        }
                    });
                    
                    return items;
                }
            """)
            
            # Filter out already seen articles
            for article in articles:
                article_id = self.generate_article_id(article['url'])
                
                if article_id not in self.seen_articles:
                    article['id'] = article_id
                    article['scraped_at'] = datetime.now().isoformat()
                    article['source'] = 'LiveMint'
                    
                    new_articles.append(article)
                    self.seen_articles.add(article_id)
            
            if new_articles:
                print(f'    ✅ Found {len(new_articles)} new articles')
            else:
                print(f'    ℹ️  No new articles')
                
        except Exception as e:
            print(f'    ❌ Error scraping {section_url}: {str(e)[:100]}')
        
        return new_articles
    
    async def check_for_news(self, deep_scrape=False):
        """Single check cycle - scrape all sections
        
        Args:
            deep_scrape: If True, performs deep scraping to get all available articles
        """
        print(f'\n{"="*70}')
        if deep_scrape:
            print(f'🔍 BULK DOWNLOAD Started: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'📥 Mode: Deep Scraping (Loading ALL articles)')
        else:
            print(f'🔍 News Check Started: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'{"="*70}')
        
        # Random user agent
        desktop_uas = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        user_agent = random.choice(desktop_uas)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.config['headless'],
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context = await browser.new_context(
                user_agent=user_agent,
                viewport=self.config['viewport'],
                locale='en-IN',
                timezone_id='Asia/Kolkata',
            )
            
            # Anti-detection scripts
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}};
            """)
            
            page = await context.new_page()
            
            total_new_articles = []
            
            try:
                # Check each section
                for section_url in self.config['sections']:
                    new_articles = await self.scrape_section(page, section_url, deep_scrape=deep_scrape)
                    total_new_articles.extend(new_articles)
                    
                    # Random delay between sections
                    if deep_scrape:
                        # Longer delay for bulk mode
                        delay = random.randint(5000, 10000)
                    else:
                        delay = random.randint(3000, 6000)
                    
                    await page.wait_for_timeout(delay)
                
                # Save new articles
                if total_new_articles:
                    self.all_articles.extend(total_new_articles)
                    self.save_articles()
                    self.save_seen_articles()
                    
                    print(f'\n✅ Total new articles: {len(total_new_articles)}')
                    print(f'📊 Total articles in database: {len(self.all_articles)}')
                else:
                    print(f'\nℹ️  No new articles found in this cycle')
            
            except Exception as e:
                print(f'\n❌ Error during news check: {str(e)}')
            
            finally:
                await browser.close()
        
        print(f'{"="*70}')
        return len(total_new_articles)
    
    async def bulk_download_all(self):
        """Bulk download mode - scrape all available articles from all sections"""
        print('🚀 LiveMint Bulk Download Mode')
        print('📥 This will scrape ALL available articles from each section')
        print('⏱️  This may take 10-30 minutes depending on how many articles exist')
        print()
        
        # Perform deep scrape
        await self.check_for_news(deep_scrape=True)
        
        print(f'\n{"="*70}')
        print('✅ BULK DOWNLOAD COMPLETE')
        print(f'📊 Total articles downloaded: {len(self.all_articles)}')
        print(f'💾 Saved to: {self.config["output_file"]}')
        print(f'{"="*70}')
    
    async def run_bulk_then_continuous(self):
        """First download all existing articles, then switch to continuous monitoring"""
        print('🚀 LiveMint Monitor - BULK + CONTINUOUS Mode')
        print()
        print('Phase 1: Bulk Download - Scraping all existing articles...')
        print('Phase 2: Continuous Monitoring - Will start after bulk download')
        print(f'{"="*70}')
        
        # Phase 1: Bulk download
        await self.bulk_download_all()
        
        print('\n\n' + '='*70)
        print('🔄 SWITCHING TO CONTINUOUS MONITORING MODE')
        print(f'⏰ Will check for new articles every {self.config["check_interval"]} seconds')
        print('='*70)
        
        await asyncio.sleep(5)  # Brief pause before starting continuous mode
        
        # Phase 2: Continuous monitoring
        cycle_count = 0
        
        try:
            while True:
                cycle_count += 1
                print(f'\n[Continuous Mode - Cycle #{cycle_count}]')
                
                # Perform normal check (not deep scrape)
                await self.check_for_news(deep_scrape=False)
                
                # Wait before next check
                wait_time = self.config['check_interval'] + random.randint(-30, 30)
                next_check = datetime.now().timestamp() + wait_time
                next_check_time = datetime.fromtimestamp(next_check).strftime('%H:%M:%S')
                
                print(f'\n⏳ Sleeping for {wait_time} seconds (Next check: {next_check_time})')
                await asyncio.sleep(wait_time)
        
        except KeyboardInterrupt:
            print('\n\n⚠️  Monitor stopped by user (Ctrl+C)')
            print(f'📊 Continuous cycles completed: {cycle_count}')
            print(f'📊 Total articles collected: {len(self.all_articles)}')
    
    async def run_continuous(self):
        """Run continuous monitoring 24/7"""
        print('🚀 LiveMint News Monitor Started (Continuous Mode)')
        print(f'⏰ Check Interval: {self.config["check_interval"]} seconds')
        print(f'📂 Output File: {self.config["output_file"]}')
        print(f'🔗 Monitoring Sections: {len(self.config["sections"])}')
        
        cycle_count = 0
        
        try:
            while True:
                cycle_count += 1
                print(f'\n[Cycle #{cycle_count}]')
                
                # Perform news check
                await self.check_for_news()
                
                # Wait before next check
                wait_time = self.config['check_interval'] + random.randint(-30, 30)
                next_check = datetime.now().timestamp() + wait_time
                next_check_time = datetime.fromtimestamp(next_check).strftime('%H:%M:%S')
                
                print(f'\n⏳ Sleeping for {wait_time} seconds (Next check: {next_check_time})')
                await asyncio.sleep(wait_time)
        
        except KeyboardInterrupt:
            print('\n\n⚠️  Monitor stopped by user (Ctrl+C)')
            print(f'📊 Total cycles completed: {cycle_count}')
            print(f'📊 Total articles collected: {len(self.all_articles)}')
    
    async def run_once(self):
        """Run single check (for testing or scheduled tasks)"""
        print('🚀 LiveMint News Monitor - Single Check Mode')
        await self.check_for_news(deep_scrape=False)
        print(f'\n✅ Check complete. Total articles: {len(self.all_articles)}')


async def main():
    """Main entry point"""
    import sys
    
    # Configuration
    config = {
        'check_interval': 300,  # 5 minutes (adjust as needed)
        'sections': [
            'https://www.livemint.com/market',
            'https://www.livemint.com/companies',
            'https://www.livemint.com/money',
            'https://www.livemint.com/news',
        ],
        'output_file': 'livemint_news.json',
        'seen_articles_file': 'seen_articles.json',
        'viewport': {'width': 1536, 'height': 864},
        'headless': True,  # Set to False for debugging
    }
    
    # Create monitor instance
    monitor = LiveMintNewsMonitor(config)
    
    # Check command line args
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == '--once':
            # Run single check
            await monitor.run_once()
        
        elif mode == '--bulk':
            # Bulk download all articles
            await monitor.bulk_download_all()
        
        elif mode == '--bulk-continuous' or mode == '--all':
            # Bulk download first, then continuous monitoring
            await monitor.run_bulk_then_continuous()
        
        else:
            print(f'Unknown mode: {mode}')
            print('\nAvailable modes:')
            print('  (no args)           - Continuous monitoring only')
            print('  --once              - Single check only')
            print('  --bulk              - Bulk download all articles once')
            print('  --bulk-continuous   - Bulk download + continuous monitoring (RECOMMENDED)')
            print('  --all               - Same as --bulk-continuous')
    
    else:
        # Default: Run continuous monitoring
        await monitor.run_continuous()


if __name__ == '__main__':
    asyncio.run(main())
