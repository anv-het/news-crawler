import asyncio
import json
import sys
import random
from pathlib import Path
from collections import Counter
from playwright.async_api import async_playwright

async def human_type(page, selector, text, move_mouse_before=True):
    """Simulate human-like typing. Optionally move mouse to the selector first."""
    await page.wait_for_selector(selector)
    if move_mouse_before:
        try:
            await move_mouse_to_selector(page, selector)
        except Exception:
            pass
    await page.focus(selector)
    for char in text:
        await page.keyboard.type(char, delay=random.randint(50, 150))

async def move_mouse_to_selector(page, selector):
    """Move mouse in a human-like path to the center of selector.
    Uses multiple small movements and short pauses to mimic real mouse movement.
    """
    # Get element center coordinates in viewport
    coords = await page.evaluate("""
        (sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        }
    """, selector)

    if not coords:
        return

    target_x = coords['x']
    target_y = coords['y']

    # Get viewport size to clamp coordinates
    vp = await page.evaluate("() => ({ w: window.innerWidth, h: window.innerHeight })")
    target_x = max(1, min(vp['w'] - 1, target_x))
    target_y = max(1, min(vp['h'] - 1, target_y))

    # Move in a few segments with small random offsets to look natural
    segments = random.randint(6, 14)
    # start from current mouse position approximation: move from center
    start = await page.evaluate("() => ({ x: window.innerWidth / 2, y: window.innerHeight / 2 })")
    cur_x = start['x']
    cur_y = start['y']

    for i in range(1, segments + 1):
        # linear interpolate
        nx = cur_x + (target_x - cur_x) * (i / segments)
        ny = cur_y + (target_y - cur_y) * (i / segments)
        # add small random jitter
        jitter_x = random.uniform(-8, 8)
        jitter_y = random.uniform(-8, 8)
        try:
            await page.mouse.move(nx + jitter_x, ny + jitter_y, steps=random.randint(4, 8))
        except Exception:
            # fallback single move
            try:
                await page.mouse.move(target_x, target_y)
            except Exception:
                pass
        await page.wait_for_timeout(random.randint(30, 120))

    # final precise move
    try:
        await page.mouse.move(target_x, target_y, steps=random.randint(4, 8))
    except Exception:
        pass

    # small idle before interacting
    await page.wait_for_timeout(random.randint(120, 350))

async def scroll_page_naturally(page, with_delay=False, speed='medium'):
    """Scroll down the page naturally to simulate reading with mouse movement and variable pauses.
    
    Args:
        page: Playwright page
        with_delay: if True, add longer reading pauses
        speed: 'slow', 'medium', or 'fast' scrolling
    """
    # Determine viewport to position mouse
    vp = await page.evaluate("() => ({ w: window.innerWidth, h: window.innerHeight })")

    # Adjust scroll parameters based on speed
    if speed == 'slow':
        scroll_steps = random.randint(5, 9)
        scroll_amount_range = (150, 350)
        pause_range = (1500, 3000)
    elif speed == 'fast':
        scroll_steps = random.randint(2, 4)
        scroll_amount_range = (400, 800)
        pause_range = (300, 800)
    else:  # medium
        scroll_steps = random.randint(3, 6)
        scroll_amount_range = (200, 600)
        pause_range = (600, 1400)

    for i in range(scroll_steps):
        scroll_amount = random.randint(*scroll_amount_range)
        # Smooth scroll using JS
        await page.evaluate(f"window.scrollBy({{ top: {scroll_amount}, behavior: 'smooth' }})")

        # Move mouse to a reading position (random x within center area, y mid viewport)
        try:
            rx = random.randint(int(vp['w'] * 0.2), int(vp['w'] * 0.8))
            ry = random.randint(int(vp['h'] * 0.3), int(vp['h'] * 0.8))
            await page.mouse.move(rx + random.uniform(-10, 10), ry + random.uniform(-10, 10), steps=random.randint(6, 12))
        except Exception:
            pass

        # Reading pause: longer if with_delay
        if with_delay:
            # longer attention on some steps
            await page.wait_for_timeout(random.randint(1200, 3500))
            # occasionally move mouse a bit to simulate reading
            if random.random() > 0.5:
                try:
                    await page.mouse.move(rx + random.uniform(-60, 60), ry + random.uniform(-40, 40), steps=random.randint(4, 8))
                except Exception:
                    pass
                await page.wait_for_timeout(random.randint(500, 1200))
        else:
            await page.wait_for_timeout(random.randint(*pause_range))

    # Occasionally scroll back a bit to mimic re-reading
    if random.random() > 0.4:
        back = random.randint(100, 300)
        await page.evaluate(f"window.scrollBy({{ top: -{back}, behavior: 'smooth' }})")
        await page.wait_for_timeout(random.randint(400, 900))

    # Final small pause
    await page.wait_for_timeout(random.randint(400, 1000))

async def scroll_to_bottom_then_up(page):
    """Scroll slowly to bottom, then scroll back up slowly and return to a middle position."""
    print('    📜 Scrolling to bottom then back up...')
    vp = await page.evaluate("() => ({ w: window.innerWidth, h: window.innerHeight })")
    
    # Scroll down slowly to bottom
    scroll_steps_down = random.randint(6, 10)
    for i in range(scroll_steps_down):
        scroll_amount = random.randint(250, 450)
        await page.evaluate(f"window.scrollBy({{ top: {scroll_amount}, behavior: 'smooth' }})")
        
        # Move mouse while scrolling
        try:
            rx = random.randint(int(vp['w'] * 0.3), int(vp['w'] * 0.7))
            ry = random.randint(int(vp['h'] * 0.4), int(vp['h'] * 0.7))
            await page.mouse.move(rx, ry, steps=random.randint(5, 10))
        except Exception:
            pass
        
        await page.wait_for_timeout(random.randint(800, 1800))
    
    # Pause at bottom
    await page.wait_for_timeout(random.randint(1000, 2500))
    
    # Scroll back up slowly
    scroll_steps_up = random.randint(4, 7)
    for i in range(scroll_steps_up):
        scroll_amount = random.randint(-300, -500)
        await page.evaluate(f"window.scrollBy({{ top: {scroll_amount}, behavior: 'smooth' }})")
        await page.wait_for_timeout(random.randint(700, 1500))
    
    # Final pause
    await page.wait_for_timeout(random.randint(500, 1200))

async def hover_and_click_links(page, context, open_tabs=True, weight=1, scroll_in_tab=False):
    """Hover over some search result links and open more tabs for frequently-searched queries.

    Args:
        page: Playwright page
        context: Playwright context (used to open new pages)
        open_tabs: allow opening tabs
        weight: integer indicating how frequently this query appears (higher -> open more)
        scroll_in_tab: if True, scroll in opened tabs like a human
    """
    try:
        results = await page.query_selector_all('li.b_algo h2 a')
        if results and len(results) > 0:
            # Increase number of hover candidates when weight is higher
            max_hovers = 2 + min(6, weight * 2)
            num_hovers = min(random.randint(2, max_hovers), len(results))
            selected_links = random.sample(results, num_hovers)

            tabs_opened = 0
            # Base max tabs 1-3, then add more capacity for higher weight (capped)
            base_max = random.randint(1, 3)
            max_tabs = min(6, base_max + max(0, weight - 1)) if open_tabs else 0

            # Probabilities scaled by weight
            prob_first = min(0.98, 0.7 + 0.2 + 0.05 * (weight - 1))  # starts ~0.9
            prob_others = min(0.95, 0.6 + 0.2 + 0.05 * (weight - 1))  # starts ~0.8

            for idx, link in enumerate(selected_links):
                await link.hover()
                await page.wait_for_timeout(random.randint(600, 1400))

                if not open_tabs:
                    continue

                # Decide whether to open this link in new tab
                if idx == 0:
                    should_open = (random.random() < prob_first)
                else:
                    should_open = (tabs_opened < max_tabs) and (random.random() < prob_others)

                if should_open and tabs_opened < max_tabs:
                    try:
                        href = await link.get_attribute('href')
                        if href:
                            print(f'    📂 Opening link in new tab: {href[:120]}...')

                            new_page = await context.new_page()
                            await new_page.goto(href, wait_until='domcontentloaded', timeout=25000)

                            # Decide behavior in tab: scroll or just wait
                            if scroll_in_tab and random.random() > 0.4:
                                print(f'       📜 Scrolling in tab...')
                                speed = random.choice(['slow', 'medium', 'fast'])
                                await scroll_page_naturally(new_page, with_delay=False, speed=speed)
                            else:
                                # Just wait (simulate reading)
                                min_wait = 2000 + (weight - 1) * 500
                                max_wait = 4000 + (weight - 1) * 1000
                                await new_page.wait_for_timeout(random.randint(max(1500, min_wait), max_wait))

                            await new_page.close()
                            tabs_opened += 1
                            print(f'    ✅ Closed tab ({tabs_opened}/{max_tabs})')

                            await page.wait_for_timeout(random.randint(300, 900))
                    except Exception as e:
                        print(f'    ⚠️  Failed to open tab: {str(e)[:120]}')
                        pass
    except Exception as e:
        print(f'    ⚠️  Error in hover_and_click_links: {str(e)[:120]}')

async def click_first_result(page, context):
    """Click on the first search result and stay for a while"""
    try:
        results = await page.query_selector_all('li.b_algo h2 a')
        if results and len(results) > 0:
            first_link = results[0]
            href = await first_link.get_attribute('href')
            
            if href:
                print(f'    🖱️  Clicking first result: {href[:60]}...')
                
                # Hover first
                await first_link.hover()
                await page.wait_for_timeout(random.randint(500, 1000))
                
                # Open in new tab
                new_page = await context.new_page()
                await new_page.goto(href, wait_until='domcontentloaded', timeout=15000)
                
                # Stay longer on first result (3-6 seconds)
                await new_page.wait_for_timeout(random.randint(3000, 6000))
                
                # Close the tab
                await new_page.close()
                print(f'    ✅ Closed first result tab')
                
                await page.wait_for_timeout(random.randint(500, 1000))
    except Exception as e:
        print(f'    ⚠️  Failed to click first result: {str(e)[:50]}')

async def scrape_current_page(page):
    """Extract search results from current page"""
    return await page.evaluate("""
        () => {
            const items = [];
            const resultElements = document.querySelectorAll('li.b_algo');
            
            resultElements.forEach(el => {
                const titleEl = el.querySelector('h2');
                const linkEl = el.querySelector('h2 a');
                let snippet = '';
                
                // Snippet extraction logic
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
                    
                    // Simple URL decode
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
        }
    """)

async def open_two_links_sequentially(page, context, weight=1):
    """Open two links one after another: first link, wait, then second link with slow scroll."""
    try:
        results = await page.query_selector_all('li.b_algo h2 a')
        if results and len(results) >= 2:
            print('    🔗 Opening two links sequentially...')
            
            # Select first two results
            links_to_open = results[:2]
            
            for idx, link in enumerate(links_to_open):
                href = await link.get_attribute('href')
                if href:
                    print(f'    📂 Opening link {idx+1}/2: {href[:80]}...')
                    
                    # Hover first
                    await link.hover()
                    await page.wait_for_timeout(random.randint(500, 1000))
                    
                    # Open in new tab
                    new_page = await context.new_page()
                    await new_page.goto(href, wait_until='domcontentloaded', timeout=20000)
                    
                    if idx == 0:
                        # First link: just wait
                        wait_time = random.randint(3000, 5000)
                        print(f'       ⏳ Waiting {wait_time/1000:.1f}s on first link...')
                        await new_page.wait_for_timeout(wait_time)
                    else:
                        # Second link: scroll slowly
                        print(f'       📜 Scrolling slowly on second link...')
                        await scroll_page_naturally(new_page, with_delay=True, speed='slow')
                    
                    await new_page.close()
                    print(f'    ✅ Closed link {idx+1}/2')
                    
                    # Pause between opening links
                    if idx == 0:
                        await page.wait_for_timeout(random.randint(800, 1500))
                        
    except Exception as e:
        print(f'    ⚠️  Failed to open sequential links: {str(e)[:100]}')

async def scroll_to_end_then_click(page, context):
    """Scroll to end of search results, then click a random link."""
    try:
        print('    📜 Scrolling to end of results...')
        
        # Scroll down to end
        for i in range(random.randint(4, 7)):
            await page.evaluate("window.scrollBy({ top: 400, behavior: 'smooth' })")
            await page.wait_for_timeout(random.randint(600, 1200))
        
        # Pause at bottom
        await page.wait_for_timeout(random.randint(1000, 2000))
        
        # Get visible results
        results = await page.query_selector_all('li.b_algo h2 a')
        if results and len(results) > 2:
            # Pick a random link (avoid first to simulate browsing)
            link = random.choice(results[2:min(8, len(results))])
            href = await link.get_attribute('href')
            
            if href:
                print(f'    🖱️  Clicking link at bottom: {href[:80]}...')
                
                # Scroll to make it visible if needed
                await link.scroll_into_view_if_needed()
                await page.wait_for_timeout(random.randint(300, 700))
                
                # Hover and click
                await link.hover()
                await page.wait_for_timeout(random.randint(500, 1000))
                
                new_page = await context.new_page()
                await new_page.goto(href, wait_until='domcontentloaded', timeout=20000)
                
                # Stay for a bit
                await new_page.wait_for_timeout(random.randint(3000, 6000))
                
                await new_page.close()
                print(f'    ✅ Closed clicked link')
                
    except Exception as e:
        print(f'    ⚠️  Failed scroll-to-end-then-click: {str(e)[:100]}')

async def main():
    print('--- Bing Search Scraper (Stealth Mode - Python) ---')

    # Parse command-line args similar to crawler.js: accept CSV file, JSON array, or single string
    args = sys.argv[1:]
    queries = []

    if args:
        input_arg = args[0]
        if input_arg.lower().endswith('.csv'):
            path = Path(input_arg)
            if path.exists():
                try:
                    print(f'Reading queries from CSV: {input_arg}')
                    with open(path, 'r', encoding='utf-8') as f:
                        lines = [line.strip() for line in f.read().splitlines() if line.strip()]
                        queries = lines
                        if queries and queries[0].lower() in ['query', 'keywords']:
                            queries.pop(0)
                except Exception as e:
                    print('Error reading CSV:', e)
                    sys.exit(1)
            else:
                print(f'File not found: {input_arg}')
                sys.exit(1)
        else:
            try:
                parsed = json.loads(input_arg)
                if isinstance(parsed, list):
                    queries = parsed
                else:
                    queries = [input_arg]
            except Exception:
                queries = [input_arg]
    else:
        queries = ['AI agent frameworks']  # Default

    if len(queries) == 0:
        print('No queries found to process.')
        return

    # Compute how often each query appears so we can bias behavior for frequently-searched terms
    query_weights = Counter(queries)

    print(f'Processing {len(queries)} queries:', queries)

    # Pick a random desktop user-agent (small built-in list to avoid external deps)
    desktop_uas = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.96 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15'
    ]
    user_agent = random.choice(desktop_uas)
    print(f'Using User-Agent: {user_agent}')

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--window-size=1536,864',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={
                'width': 1536,
                'height': 864
            },
            locale='en-US',
            timezone_id='Asia/Kolkata',
            permissions=['geolocation'],
            # Additional fingerprinting resistance
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        
        # Hide webdriver traces
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            window.chrome = {
                runtime: {}
            };
        """)
        
        page = await context.new_page()

        # Try stealth if available
        try:
            import playwright_stealth
            await playwright_stealth.stealth_async(page)
            print('✅ Stealth mode activated')
        except Exception:
            print('⚠️  Continuing without stealth mode')

        all_results = {}

        try:
            await page.goto('https://www.bing.com', wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(2000 + random.randint(500, 2000))

            # Cookie consent
            try:
                accept_btn = page.get_by_role('button', name='Accept')
                if await accept_btn.is_visible():
                    await accept_btn.click()
                    await page.wait_for_timeout(500)
            except Exception:
                pass

            for query in queries:
                print(f"\n--- Searching for: \"{query}\" ---")
                all_results[query] = []
                
                # Random delay before starting search (2-5 seconds)
                delay_before_search = random.randint(2000, 5000)
                print(f'⏳ Waiting {delay_before_search/1000:.1f}s before searching...')
                await page.wait_for_timeout(delay_before_search)

                try:
                    await page.goto('https://www.bing.com')
                    await page.wait_for_timeout(1000 + random.random() * 1000)

                    search_selectors = ['textarea#sb_form_q', 'input#sb_form_q', '[name="q"]']
                    typed = False
                    for sel in search_selectors:
                        try:
                            if await page.locator(sel).first.is_visible():
                                # Hover over search box first
                                await page.locator(sel).first.hover()
                                await page.wait_for_timeout(random.randint(300, 600))
                                
                                # Click and focus
                                await page.locator(sel).first.click()
                                await page.wait_for_timeout(random.randint(200, 400))
                                
                                # Clear existing text first
                                await page.locator(sel).first.fill('')
                                await human_type(page, sel, query)
                                typed = True
                                break
                        except Exception:
                            continue

                    if not typed:
                        print('Could not find search box')
                        continue

                    await page.wait_for_timeout(500)
                    await page.keyboard.press('Enter')
                    print('Waiting for Page 1...')
                    
                    # Check for CAPTCHA
                    try:
                        captcha_detected = await page.locator('text="One last step"').is_visible(timeout=3000)
                        if captcha_detected:
                            print('⚠️  CAPTCHA detected! Waiting 30 seconds for manual solve...')
                            print('    👉 Please solve the CAPTCHA in the browser window')
                            await page.wait_for_timeout(30000)
                            # Check if still on captcha page
                            still_captcha = await page.locator('text="One last step"').is_visible(timeout=2000)
                            if still_captcha:
                                print('    ⚠️  CAPTCHA not solved, skipping this query')
                                continue
                            else:
                                print('    ✅ CAPTCHA solved, continuing...')
                    except Exception:
                        pass  # No CAPTCHA, continue normally
                    
                    await page.wait_for_selector('li.b_algo', timeout=15000)
                    
                    # Random behavior pattern with more variety (including new patterns)
                    behavior_pattern = random.choice([
                        'scroll_slow', 'scroll_fast', 'scroll_medium',
                        'scroll_then_open_tabs', 'open_tabs_with_scroll',
                        'two_links_sequential', 'scroll_to_end_click',
                        'scroll_down_up_click', 'click_first'
                    ])
                    print(f'🎭 Behavior: {behavior_pattern}')
                    
                    await page.wait_for_timeout(random.randint(1000, 2000))
                    
                    if behavior_pattern == 'scroll_slow':
                        print('    📜 Scrolling slowly...')
                        await scroll_page_naturally(page, with_delay=True, speed='slow')
                        
                    elif behavior_pattern == 'scroll_fast':
                        print('    📜 Scrolling fast...')
                        await scroll_page_naturally(page, with_delay=False, speed='fast')
                        
                    elif behavior_pattern == 'scroll_medium':
                        print('    📜 Scrolling at medium pace...')
                        await scroll_page_naturally(page, with_delay=False, speed='medium')
                        
                    elif behavior_pattern == 'scroll_then_open_tabs':
                        print('    📜 Scrolling first, then opening tabs...')
                        await scroll_page_naturally(page, with_delay=False, speed='medium')
                        await hover_and_click_links(page, context, open_tabs=True, weight=query_weights[query], scroll_in_tab=False)
                        
                    elif behavior_pattern == 'open_tabs_with_scroll':
                        print('    📜 Opening tabs and scrolling inside them...')
                        await scroll_page_naturally(page, with_delay=False, speed='medium')
                        await hover_and_click_links(page, context, open_tabs=True, weight=query_weights[query], scroll_in_tab=True)
                        
                    elif behavior_pattern == 'two_links_sequential':
                        await open_two_links_sequentially(page, context, weight=query_weights[query])
                        
                    elif behavior_pattern == 'scroll_to_end_click':
                        await scroll_to_end_then_click(page, context)
                        
                    elif behavior_pattern == 'scroll_down_up_click':
                        await scroll_to_bottom_then_up(page)
                        # After scrolling up, click a random visible link
                        try:
                            results = await page.query_selector_all('li.b_algo h2 a')
                            if results and len(results) > 1:
                                link = random.choice(results[1:min(5, len(results))])
                                href = await link.get_attribute('href')
                                if href:
                                    print(f'    🖱️  Clicking link after scroll: {href[:80]}...')
                                    await link.hover()
                                    await page.wait_for_timeout(random.randint(500, 1000))
                                    new_page = await context.new_page()
                                    await new_page.goto(href, wait_until='domcontentloaded', timeout=20000)
                                    await new_page.wait_for_timeout(random.randint(2000, 4000))
                                    await new_page.close()
                        except Exception as e:
                            print(f'    ⚠️  Failed to click after scroll: {str(e)[:80]}')
                        
                    elif behavior_pattern == 'click_first':
                        print('    🖱️  Quick click on first result...')
                        await click_first_result(page, context)

                    # Page 1
                    page1 = await scrape_current_page(page)
                    all_results[query].extend(page1)
                    print(f'  Page 1: Found {len(page1)} results')

                    # Page 2
                    try:
                        next_button = page.locator('a[title="Next page"], a[aria-label="Page 2"]')
                        if await next_button.first.is_visible():
                            print('Navigating to Page 2...')
                            
                            # Hover before clicking
                            await next_button.first.hover()
                            await page.wait_for_timeout(random.randint(500, 1000))
                            
                            await next_button.first.click()
                            await page.wait_for_timeout(2000 + random.random() * 2000)
                            await page.wait_for_selector('li.b_algo', timeout=15000)
                            
                            # Use similar pattern for page 2 (but simpler - just scroll)
                            await page.wait_for_timeout(random.randint(1000, 2000))
                            page2_behavior = random.choice(['scroll', 'scroll_and_hover'])
                            
                            if page2_behavior == 'scroll':
                                print('    📜 Scrolling page 2...')
                                await scroll_page_naturally(page, with_delay=False)
                            else:
                                print('    📜 Scrolling page 2 and hovering...')
                                await scroll_page_naturally(page, with_delay=False)
                                await hover_and_click_links(page, context, open_tabs=False, weight=query_weights[query])
                            
                            page2 = await scrape_current_page(page)
                            all_results[query].extend(page2)
                            print(f'  Page 2: Found {len(page2)} results')
                    except Exception as e:
                        print('  No Page 2 found or validation error:', str(e))

                except Exception as err:
                    print(f'Error processing "{query}": {err}')

                # Pause between queries
                await page.wait_for_timeout(2000 + random.random() * 3000)

            # Save results
            with open('cwaler_python_results.json', 'w', encoding='utf-8') as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)
            print('\nSuccess! Saved results to cwaler_python_results.json')

        except Exception as err:
            print('Fatal Scraper Error:', err)
        finally:
            await browser.close()

if __name__ == '__main__':
    asyncio.run(main())