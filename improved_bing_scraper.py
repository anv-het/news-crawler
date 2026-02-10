"""
Improved Bing Scraper - Python version with enhanced anti-detection
Based on the successful JavaScript implementation
"""
import asyncio
import json
import random
import sys
from pathlib import Path
from playwright.async_api import async_playwright

async def human_type(page, selector, text):
    """Type with human-like delays"""
    await page.wait_for_selector(selector)
    await page.focus(selector)
    for char in text:
        await page.keyboard.type(char, delay=random.randint(50, 150))

async def random_mouse_move(page):
    """Random mouse movement to simulate human behavior"""
    try:
        x = random.randint(100, 900)
        y = random.randint(100, 600)
        await page.mouse.move(x, y, steps=10)
    except Exception:
        pass

async def scrape_current_page(page):
    """Extract search results from current page"""
    return await page.evaluate("""() => {
        const items = [];
        const resultElements = document.querySelectorAll('li.b_algo');
        
        resultElements.forEach(el => {
            const titleEl = el.querySelector('h2');
            const linkEl = el.querySelector('h2 a');
            
            let snippet = '';
            // Try multiple snippet selectors
            const snippetSelectors = ['.b_caption p', '.b_snippet', '.b_algoSlug', '.b_lineclamp2'];
            for (const sel of snippetSelectors) {
                const found = el.querySelector(sel);
                if (found && found.innerText.trim().length > 0) {
                    snippet = found.innerText.trim();
                    break;
                }
            }
            if (!snippet) {
                const caption = el.querySelector('.b_caption');
                if (caption) {
                    const clone = caption.cloneNode(true);
                    clone.querySelectorAll('cite, .b_attribution').forEach(e => e.remove());
                    snippet = clone.innerText.trim();
                }
            }
            
            if (titleEl && linkEl) {
                let finalUrl = linkEl.href;
                // Decode Bing redirect URLs
                try {
                    const urlObj = new URL(finalUrl);
                    if (urlObj.pathname.includes('/ck/a')) {
                        const u = urlObj.searchParams.get('u');
                        if (u) {
                            let enc = u.startsWith('a1') ? u.substring(2) : u;
                            enc = enc.replace(/-/g, '+').replace(/_/g, '/');
                            while (enc.length % 4) enc += '=';
                            finalUrl = atob(enc);
                        }
                    }
                } catch (e) {}
                
                items.push({
                    title: titleEl.innerText,
                    url: finalUrl,
                    snippet: snippet
                });
            }
        });
        return items;
    }""")

async def main():
    print('=== Improved Bing Search Scraper ===\n')
    
    # Parse arguments
    args = sys.argv[1:]
    queries = []
    
    if len(args) > 0:
        input_arg = args[0]
        if input_arg.endswith('.csv'):
            csv_path = Path(input_arg)
            if csv_path.exists():
                print(f'📂 Reading queries from CSV: {input_arg}')
                content = csv_path.read_text(encoding='utf-8')
                queries = [line.strip() for line in content.split('\n') if line.strip()]
                # Remove header if present
                if queries and queries[0].lower() in ['query', 'keywords']:
                    queries.pop(0)
            else:
                print(f'❌ File not found: {input_arg}')
                sys.exit(1)
        else:
            # Treat as JSON array or single string
            try:
                parsed = json.loads(input_arg)
                queries = parsed if isinstance(parsed, list) else [input_arg]
            except json.JSONDecodeError:
                queries = [input_arg]
    else:
        queries = ['AI agent frameworks']  # Default
    
    if not queries:
        print('⚠️  No queries found to process.')
        sys.exit(0)
    
    print(f'📋 Processing {len(queries)} queries:\n   {", ".join(queries[:5])}'
          f'{"..." if len(queries) > 5 else ""}\n')
    
    all_results = {}
    
    async with async_playwright() as p:
        # CRITICAL: Use playwright-stealth-like settings
        # Playwright-extra stealth plugin features replicated
        browser = await p.chromium.launch(
            headless=False,  # Keep browser visible to avoid headless detection
            args=[
                '--disable-blink-features=AutomationControlled',  # KEY: Remove automation flag
                '--disable-dev-shm-usage',
                '--disable-setuid-sandbox',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--allow-running-insecure-content',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
            ]
        )
        
        # Randomize viewport size
        viewport_width = 1280 + random.randint(0, 100)
        viewport_height = 720 + random.randint(0, 100)
        
        # Realistic user agents (Desktop browsers)
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15',
        ]
        selected_ua = random.choice(user_agents)
        print(f'🌐 User-Agent: {selected_ua[:60]}...\n')
        
        context = await browser.new_context(
            user_agent=selected_ua,
            viewport={'width': viewport_width, 'height': viewport_height},
            locale='en-US',
            timezone_id='America/New_York',
            # Permissions to appear more like real browser
            permissions=['geolocation', 'notifications'],
            # Override navigator.webdriver property
            java_script_enabled=True,
        )
        
        # CRITICAL: Override webdriver and other automation flags
        await context.add_init_script("""
            // Override the navigator.webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override the Permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Override plugins to add fake ones
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Chrome runtime
            window.chrome = {
                runtime: {}
            };
        """)
        
        page = await context.new_page()
        
        try:
            # Initial load
            print('🔄 Loading Bing homepage...')
            await page.goto('https://www.bing.com', wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(random.randint(2000, 3000))
            
            # Handle cookie consent
            try:
                accept_btn = page.get_by_role('button', name='Accept')
                if await accept_btn.is_visible(timeout=3000):
                    await accept_btn.click()
                    print('✅ Cookie consent accepted')
                    await page.wait_for_timeout(500)
            except Exception:
                pass
            
            # Process each query
            for idx, query in enumerate(queries, 1):
                print(f'\n{"="*70}')
                print(f'🔍 Query {idx}/{len(queries)}: "{query}"')
                print(f'{"="*70}')
                all_results[query] = []
                
                try:
                    # Go back to homepage for each new search
                    await page.goto('https://www.bing.com', wait_until='domcontentloaded')
                    await page.wait_for_timeout(random.randint(1000, 2000))
                    
                    # Random mouse movement before search
                    await random_mouse_move(page)
                    
                    # Find and type in search box
                    search_selectors = ['textarea#sb_form_q', 'input#sb_form_q', '[name="q"]']
                    typed = False
                    
                    for selector in search_selectors:
                        try:
                            if await page.locator(selector).first.is_visible(timeout=2000):
                                print(f'   ⌨️  Typing query...')
                                await human_type(page, selector, query)
                                typed = True
                                break
                        except Exception:
                            continue
                    
                    if not typed:
                        print('   ❌ Could not find search box, skipping...')
                        continue
                    
                    # Small delay before pressing Enter
                    await page.wait_for_timeout(random.randint(300, 700))
                    await page.keyboard.press('Enter')
                    
                    # Check for CAPTCHA immediately
                    print('   ⏳ Waiting for results...')
                    try:
                        # Check if CAPTCHA appeared
                        is_captcha = await page.locator('text="One last step"').is_visible(timeout=3000)
                        if is_captcha:
                            print('\n' + '='*70)
                            print('⚠️  ⚠️  ⚠️  CAPTCHA DETECTED  ⚠️  ⚠️  ⚠️')
                            print('='*70)
                            print('Please solve the CAPTCHA in the browser window.')
                            print('Waiting 45 seconds...')
                            print('='*70 + '\n')
                            
                            await page.wait_for_timeout(45000)
                            
                            # Check if still on CAPTCHA
                            still_captcha = await page.locator('text="One last step"').is_visible(timeout=2000)
                            if still_captcha:
                                print('   ❌ CAPTCHA not solved, skipping this query\n')
                                continue
                            else:
                                print('   ✅ CAPTCHA solved! Continuing...\n')
                    except Exception:
                        pass  # No CAPTCHA, good to go
                    
                    # Wait for results
                    await page.wait_for_selector('li.b_algo', timeout=20000)
                    print('   ✅ Results loaded')
                    
                    # Add natural delay
                    await page.wait_for_timeout(random.randint(1500, 2500))
                    
                    # Scrape Page 1
                    page1_results = await scrape_current_page(page)
                    all_results[query].extend(page1_results)
                    print(f'   📄 Page 1: Found {len(page1_results)} results')
                    
                    # Try to go to Page 2
                    try:
                        next_btn = page.locator('a[title="Next page"], a[aria-label="Page 2"]')
                        if await next_btn.first.is_visible(timeout=3000):
                            print('   🔄 Navigating to Page 2...')
                            
                            # Hover before clicking
                            await next_btn.first.hover()
                            await page.wait_for_timeout(random.randint(500, 1000))
                            
                            await next_btn.first.click()
                            await page.wait_for_timeout(random.randint(2000, 4000))
                            
                            # Wait for Page 2 results
                            await page.wait_for_selector('li.b_algo', timeout=15000)
                            
                            # Scrape Page 2
                            page2_results = await scrape_current_page(page)
                            all_results[query].extend(page2_results)
                            print(f'   📄 Page 2: Found {len(page2_results)} results')
                    except Exception as e:
                        print(f'   ℹ️  Page 2 not available: {str(e)[:50]}')
                    
                    print(f'   ✅ Total results for "{query}": {len(all_results[query])}')
                    
                except Exception as err:
                    print(f'   ❌ Error processing "{query}": {err}')
                
                # Pause between queries (important for avoiding rate limits)
                if idx < len(queries):
                    wait_time = random.randint(3000, 6000)
                    print(f'   ⏸️  Waiting {wait_time/1000:.1f}s before next query...')
                    await page.wait_for_timeout(wait_time)
            
            # Save results
            output_file = 'bing_results_python.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)
            
            print(f'\n{"="*70}')
            print(f'✅ SUCCESS! Results saved to: {output_file}')
            print(f'{"="*70}')
            
            # Summary
            total_results = sum(len(results) for results in all_results.values())
            print(f'\n📊 Summary:')
            print(f'   Total queries: {len(queries)}')
            print(f'   Total results: {total_results}')
            print(f'   Average per query: {total_results/len(queries):.1f}')
            
        except Exception as err:
            print(f'\n❌ Fatal error: {err}')
        finally:
            print('\n🔄 Closing browser...')
            await browser.close()
            print('✅ Done!\n')

if __name__ == '__main__':
    asyncio.run(main())