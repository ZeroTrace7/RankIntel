import argparse
import requests
from bs4 import BeautifulSoup
import json
import urllib.parse
from urllib.parse import urlparse
import time
from datetime import datetime
import os
import re

# Use rich for nice terminal output if available
try:
    from rich.console import Console
    console = Console()
except ImportError:
    class Console:
        def print(self, *args, **kwargs):
            print(*args)
    console = Console()

class SunriseIntelligenceEngine:
    def __init__(self, url):
        if not url.startswith("http"):
            url = "https://" + url
        self.url = url
        self.domain = urlparse(url).netloc
        self.base_url = f"{urlparse(url).scheme}://{self.domain}"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.data = {
            "technical": {},
            "on_page": {},
            "schema": [],
            "performance": {},
            "ai_crawlers": {},
            "content_aeo": {}
        }

    def fetch_page(self):
        console.print(f"[bold cyan]Fetching {self.url}...[/bold cyan]")
        try:
            start_time = time.time()
            response = requests.get(self.url, headers=self.headers, timeout=15)
            response_time = time.time() - start_time
            
            self.data["technical"]["status_code"] = response.status_code
            self.data["technical"]["response_time_sec"] = round(response_time, 2)
            self.data["technical"]["is_redirect"] = len(response.history) > 0
            
            if response.status_code == 200:
                self.html = response.text
                self.soup = BeautifulSoup(self.html, 'html.parser')
                return True
            else:
                console.print(f"[bold red]Failed to fetch page. Status: {response.status_code}[/bold red]")
                return False
        except Exception as e:
            console.print(f"[bold red]Error fetching page: {e}[/bold red]")
            return False

    def extract_on_page(self):
        console.print("[cyan]Extracting On-Page Signals...[/cyan]")
        soup = self.soup
        
        # Title
        title_tag = soup.find('title')
        title = title_tag.text.strip() if title_tag else ""
        self.data["on_page"]["title"] = title
        self.data["on_page"]["title_length"] = len(title)

        # Meta Description
        meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
        meta_desc = meta_desc_tag['content'].strip() if meta_desc_tag else ""
        self.data["on_page"]["meta_description"] = meta_desc
        self.data["on_page"]["meta_desc_length"] = len(meta_desc)

        # Headings
        h1s = [h1.text.strip() for h1 in soup.find_all('h1')]
        h2s = [h2.text.strip() for h2 in soup.find_all('h2')]
        self.data["on_page"]["h1_count"] = len(h1s)
        self.data["on_page"]["h1_text"] = h1s
        self.data["on_page"]["h2_count"] = len(h2s)
        self.data["on_page"]["h2_text"] = h2s

        # Images & Alt text
        images = soup.find_all('img')
        images_with_alt = [img for img in images if img.get('alt')]
        self.data["on_page"]["total_images"] = len(images)
        self.data["on_page"]["images_with_alt"] = len(images_with_alt)
        
        # Word Count (rough estimate of visible text)
        for script in soup(["script", "style"]):
            script.extract()
        text = soup.get_text(separator=' ')
        words = text.split()
        self.data["on_page"]["word_count"] = len(words)

    def extract_schema(self):
        console.print("[cyan]Extracting Structured Data (Schema JSON-LD)...[/cyan]")
        schema_types = []
        schema_blocks = self.soup.find_all('script', type='application/ld+json')
        
        for block in schema_blocks:
            try:
                data = json.loads(block.string)
                # Handle lists of schema
                if isinstance(data, list):
                    for item in data:
                        if '@type' in item:
                            schema_types.append(item['@type'])
                elif isinstance(data, dict):
                    if '@type' in data:
                        schema_types.append(data['@type'])
                    if '@graph' in data:
                        for item in data['@graph']:
                            if '@type' in item:
                                schema_types.append(item['@type'])
            except:
                pass
        
        # Deduplicate
        self.data["schema"] = list(set(schema_types))

    def check_ai_crawlers(self):
        console.print("[cyan]Checking AI Crawler Access (robots.txt & llms.txt)...[/cyan]")
        bots_to_check = ["Googlebot", "OAI-SearchBot", "GPTBot", "ClaudeBot", "PerplexityBot"]
        
        robots_url = f"{self.base_url}/robots.txt"
        try:
            robots_resp = requests.get(robots_url, headers=self.headers, timeout=5)
            robots_txt = robots_resp.text.lower() if robots_resp.status_code == 200 else ""
            
            for bot in bots_to_check:
                # Basic check: if 'user-agent: botname' and 'disallow: /' are present near each other
                # This is a simplified check for the evidence report
                bot_lower = bot.lower()
                status = "ALLOWED"
                if f"user-agent: {bot_lower}" in robots_txt:
                    # Very rough heuristic for explicit blocks
                    idx = robots_txt.find(f"user-agent: {bot_lower}")
                    if "disallow: /" in robots_txt[idx:idx+100]:
                        status = "BLOCKED"
                self.data["ai_crawlers"][bot] = status
        except:
            for bot in bots_to_check:
                self.data["ai_crawlers"][bot] = "UNKNOWN"

        # Check llms.txt
        llms_url = f"{self.base_url}/llms.txt"
        try:
            llms_resp = requests.get(llms_url, headers=self.headers, timeout=5)
            self.data["ai_crawlers"]["llms.txt"] = "PRESENT" if llms_resp.status_code == 200 else "MISSING"
        except:
            self.data["ai_crawlers"]["llms.txt"] = "ERROR"

    def check_performance(self):
        console.print("[cyan]Fetching Google PageSpeed Data (Mobile)...[/cyan]")
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={urllib.parse.quote(self.url)}&strategy=mobile"
        try:
            resp = requests.get(api_url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                lighthouse = data.get('lighthouseResult', {})
                metrics = lighthouse.get('audits', {})
                
                self.data["performance"]["lcp"] = metrics.get('largest-contentful-paint', {}).get('displayValue', 'N/A')
                self.data["performance"]["cls"] = metrics.get('cumulative-layout-shift', {}).get('displayValue', 'N/A')
                self.data["performance"]["tbt"] = metrics.get('total-blocking-time', {}).get('displayValue', 'N/A')
                self.data["performance"]["score"] = int(lighthouse.get('categories', {}).get('performance', {}).get('score', 0) * 100)
            else:
                self.data["performance"]["error"] = f"API Error: {resp.status_code} (Rate limited or blocked)"
        except Exception as e:
            self.data["performance"]["error"] = f"Failed to fetch PageSpeed data."

    def analyze_aeo(self):
        console.print("[cyan]Analyzing AEO (Answer Engine Optimization) Readiness...[/cyan]")
        # 1. Check for Question headings
        question_words = ['what', 'how', 'why', 'who', 'when', 'where', 'is', 'are', 'can', 'do', 'does']
        question_h2s = []
        for h2 in self.data["on_page"]["h2_text"]:
            if any(h2.lower().startswith(q) for q in question_words) or '?' in h2:
                question_h2s.append(h2)
        
        self.data["content_aeo"]["question_headings"] = question_h2s
        self.data["content_aeo"]["has_faq_schema"] = "FAQPage" in self.data["schema"]
        
        # 2. Look for lists (tables, ul/ol)
        self.data["content_aeo"]["has_tables"] = len(self.soup.find_all('table')) > 0
        self.data["content_aeo"]["has_lists"] = len(self.soup.find_all(['ul', 'ol'])) > 0

    def generate_report(self):
        domain_clean = self.domain.replace("www.", "")
        timestamp = datetime.now().strftime("%Y-%m-%d")
        report_path = f"audits/{domain_clean}-{timestamp}.md"
        
        # Ensure directory exists
        os.makedirs("audits", exist_ok=True)
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# COMPETITOR INTELLIGENCE REPORT — {self.domain}\n")
            f.write(f"**URL:** {self.url}\n")
            f.write(f"**Date:** {timestamp}\n")
            f.write(f"**Audited by:** Sunrise Intelligence Engine\n\n")
            f.write("---\n\n")

            # Technical Foundation
            f.write("## ⚙️ TECHNICAL FOUNDATION\n")
            f.write(f"- **HTTP Status Code:** {self.data['technical'].get('status_code')}\n")
            f.write(f"- **Server Response Time:** {self.data['technical'].get('response_time_sec')} seconds\n")
            f.write(f"- **Was Redirected:** {self.data['technical'].get('is_redirect')}\n\n")

            # On-Page Signals
            f.write("## 📝 ON-PAGE SIGNALS\n")
            f.write(f"- **Title Tag:** {self.data['on_page'].get('title')} ({self.data['on_page'].get('title_length')} chars)\n")
            f.write(f"- **Meta Description:** {self.data['on_page'].get('meta_description')} ({self.data['on_page'].get('meta_desc_length')} chars)\n")
            f.write(f"- **Word Count:** ~{self.data['on_page'].get('word_count')} words\n")
            f.write(f"- **H1 Tags ({self.data['on_page'].get('h1_count')}):** {', '.join(self.data['on_page'].get('h1_text'))}\n")
            
            img_total = self.data['on_page'].get('total_images')
            img_alt = self.data['on_page'].get('images_with_alt')
            img_pct = round((img_alt / img_total * 100), 1) if img_total > 0 else 0
            f.write(f"- **Image Alt Coverage:** {img_alt} / {img_total} images have alt text ({img_pct}%)\n\n")

            # Structured Data
            f.write("## 🏗️ STRUCTURED DATA (SCHEMA)\n")
            schemas = self.data['schema']
            if schemas:
                f.write(f"- **Schema Types Detected:** {', '.join(schemas)}\n")
            else:
                f.write("- **Schema Types Detected:** 🔴 NONE FOUND\n")
            f.write("\n")

            # Performance
            f.write("## 🚀 PERFORMANCE (Mobile Lab Data via Google)\n")
            perf = self.data['performance']
            if "error" in perf:
                f.write(f"- {perf['error']}\n")
            else:
                f.write(f"- **Performance Score:** {perf.get('score')}/100\n")
                f.write(f"- **Largest Contentful Paint (LCP):** {perf.get('lcp')}\n")
                f.write(f"- **Cumulative Layout Shift (CLS):** {perf.get('cls')}\n")
                f.write(f"- **Total Blocking Time (TBT):** {perf.get('tbt')}\n")
            f.write("\n")

            # AI Crawler Access
            f.write("## 🤖 AI CRAWLER ACCESS\n")
            for bot, status in self.data['ai_crawlers'].items():
                icon = "🟢" if status in ["ALLOWED", "PRESENT"] else ("🔴" if status == "BLOCKED" else "⚪")
                f.write(f"- **{bot}:** {icon} {status}\n")
            f.write("\n")

            # Content & AEO
            f.write("## 🧠 CONTENT & AEO READINESS\n")
            aeo = self.data['content_aeo']
            f.write(f"- **Has Tables (Data struct):** {'Yes' if aeo.get('has_tables') else 'No'}\n")
            f.write(f"- **Has Lists (Process steps):** {'Yes' if aeo.get('has_lists') else 'No'}\n")
            f.write(f"- **Has FAQ Schema:** {'Yes' if aeo.get('has_faq_schema') else 'No'}\n")
            
            q_headings = aeo.get('question_headings', [])
            f.write(f"- **Question-based H2s ({len(q_headings)}):**\n")
            for q in q_headings:
                f.write(f"  - {q}\n")
            f.write("\n")
            
            # Placeholder for Manual Review
            f.write("## 🔍 GAPS & RECOMMENDATIONS (Manual/AI Review Required)\n")
            f.write("*(Feed this report to the AI agent to generate specific fixes and compare against your site)*\n")

        console.print(f"\n[bold green]✅ Report successfully saved to: {report_path}[/bold green]")

    def run_audit(self):
        if self.fetch_page():
            self.extract_on_page()
            self.extract_schema()
            self.check_ai_crawlers()
            self.check_performance()
            self.analyze_aeo()
            self.generate_report()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sunrise Competitor Intelligence Engine")
    parser.add_argument("url", help="The URL to audit (e.g., https://alephindia.in)")
    args = parser.parse_args()
    
    engine = SunriseIntelligenceEngine(args.url)
    engine.run_audit()
