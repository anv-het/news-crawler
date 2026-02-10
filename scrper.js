const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth')();
const UserAgent = require('user-agents');
const fs = require('fs');

chromium.use(stealth);

(async () => {
    console.log('--- Bing Search Scraper (Stealth Mode) ---');

    // 1. Parse Arguments: Expect a CSV file path or a single query
    const args = process.argv.slice(2);
    let queries = [];

    if (args.length > 0) {
        const inputArg = args[0];
        if (inputArg.endsWith('.csv')) {
            try {
                if (fs.existsSync(inputArg)) {
                    console.log(`Reading queries from CSV: ${inputArg}`);
                    const fileContent = fs.readFileSync(inputArg, 'utf8');
                    // Split by newline, trim, and filter empty lines
                    queries = fileContent.split(/\r?\n/).map(line => line.trim()).filter(line => line.length > 0);
                    // Remove header if it looks like "query" or "keywords"
                    if (queries.length > 0 && (queries[0].toLowerCase() === 'query' || queries[0].toLowerCase() === 'keywords')) {
                        queries.shift();
                    }
                } else {
                    console.error(`File not found: ${inputArg}`);
                    process.exit(1);
                }
            } catch (e) {
                console.error('Error reading CSV:', e);
                process.exit(1);
            }
        } else {
            // Treat as raw JSON array or single string
            try {
                const parsed = JSON.parse(inputArg);
                if (Array.isArray(parsed)) queries = parsed;
                else queries = [inputArg];
            } catch (e) {
                queries = [inputArg];
            }
        }
    } else {
        queries = ['AI agent frameworks']; // Default
    }

    if (queries.length === 0) {
        console.log('No queries found to process.');
        process.exit(0);
    }

    console.log(`Processing ${queries.length} queries:`, queries);

    // 2. Launch Browser
    const userAgent = new UserAgent({ deviceCategory: 'desktop' });
    console.log(`Using User-Agent: ${userAgent.toString()}`);

    const browser = await chromium.launch({ headless: false });
    const context = await browser.newContext({
        userAgent: userAgent.toString(),
        viewport: { width: 1280 + Math.floor(Math.random() * 100), height: 720 + Math.floor(Math.random() * 100) },
        locale: 'en-US',
    });
    const page = await context.newPage();

    // Helper: Human-like typing
    async function humanType(selector, text) {
        await page.waitForSelector(selector);
        await page.focus(selector);
        for (const char of text) {
            await page.keyboard.type(char, { delay: Math.random() * 100 + 50 });
        }
    }

    // Helper: Random mouse movement
    async function randomMouseMove() {
        await page.mouse.move(Math.random() * 500, Math.random() * 500, { steps: 10 });
    }

    const allResults = {};

    try {
        // Initial load
        await page.goto('https://www.bing.com', { waitUntil: 'domcontentloaded', timeout: 60000 });
        await page.waitForTimeout(2000);

        // Cookie consent
        try {
            const acceptBtn = page.getByRole('button', { name: 'Accept' });
            if (await acceptBtn.isVisible()) {
                await acceptBtn.click();
                await page.waitForTimeout(500);
            }
        } catch (e) { }

        // Loop through queries
        for (const query of queries) {
            console.log(`\n--- Searching for: "${query}" ---`);
            allResults[query] = [];

            try {
                await page.goto('https://www.bing.com');
                await page.waitForTimeout(1000 + Math.random() * 1000);

                const searchSelectors = ['textarea#sb_form_q', 'input#sb_form_q', '[name="q"]'];
                let typed = false;
                for (const sel of searchSelectors) {
                    if (await page.locator(sel).first().isVisible()) {
                        await humanType(sel, query);
                        typed = true;
                        break;
                    }
                }

                if (!typed) {
                    console.error('Could not find search box');
                    continue;
                }

                await page.waitForTimeout(500);
                await page.keyboard.press('Enter');
                console.log('Waiting for Page 1...');
                await page.waitForSelector('li.b_algo', { timeout: 15000 });

                // Page 1
                const page1 = await scrapeCurrentPage(page);
                allResults[query].push(...page1);
                console.log(`  Page 1: Found ${page1.length} results`);

                // Page 2
                try {
                    const nextButton = page.locator('a[title="Next page"], a[aria-label="Page 2"]');
                    if (await nextButton.first().isVisible()) {
                        console.log('Navigating to Page 2...');
                        await nextButton.first().click();
                        await page.waitForTimeout(2000 + Math.random() * 2000);
                        await page.waitForSelector('li.b_algo', { timeout: 15000 });
                        const page2 = await scrapeCurrentPage(page);
                        allResults[query].push(...page2);
                        console.log(`  Page 2: Found ${page2.length} results`);
                    }
                } catch (e) {
                    console.log('  No Page 2 found or validation error:', e.message);
                }

            } catch (err) {
                console.error(`Error processing "${query}":`, err.message);
            }

            // Pause between queries
            await page.waitForTimeout(2000 + Math.random() * 3000);
        }

        fs.writeFileSync('bing_results.json', JSON.stringify(allResults, null, 2));
        console.log('\nSuccess! Saved results to bing_results.json');

    } catch (err) {
        console.error('Fatal Scraper Error:', err);
    } finally {
        await browser.close();
    }
})();

async function scrapeCurrentPage(page) {
    return await page.evaluate(() => {
        const items = [];
        const resultElements = document.querySelectorAll('li.b_algo');

        resultElements.forEach(el => {
            const titleEl = el.querySelector('h2');
            const linkEl = el.querySelector('h2 a');

            let snippet = '';
            // New snippet logic from your request
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
                // Simple decode
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
                } catch (e) { }

                items.push({
                    title: titleEl.innerText,
                    url: finalUrl,
                    snippet: snippet
                });
            }
        });
        return items;
    });
}
