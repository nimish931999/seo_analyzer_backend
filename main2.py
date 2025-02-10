from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
from typing import Any, List, Optional, Dict
import re
from urllib.parse import urlparse
import ssl
import socket
import dns.resolver
import time
from robotexclusionrulesparser import RobotExclusionRulesParser
import whois
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

from main import calculate_keyword_density

app = FastAPI(title="Advanced SEO Checker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class URLInput(BaseModel):
    url: str

class ContentAnalysis(BaseModel):
    word_count: int
    keyword_density: Dict[str, float]
    readability_score: float
    text_html_ratio: float
    heading_structure: Dict[str, List[str]]
    internal_links: List[str]
    external_links: List[str]
    broken_links: List[str]

class TechnicalAnalysis(BaseModel):
    load_time: float
    page_size: int
    ssl_info: Dict
    mobile_friendly: bool
    robots_txt: Dict
    sitemap_status: Dict
    domain_age: Optional[int]
    server_info: Dict

class MetaAnalysis(BaseModel):
    title: str
    title_length: int
    meta_description: str
    meta_description_length: int
    meta_keywords: List[str]
    canonical_url: Optional[str]
    og_tags: Dict
    twitter_tags: Dict

class ImageAnalysis(BaseModel):
    total_images: int
    images_without_alt: List[str]
    large_images: List[Dict]
    image_formats: Dict

class SEOReport(BaseModel):
    url: str
    content: ContentAnalysis
    technical: TechnicalAnalysis
    meta: MetaAnalysis
    images: ImageAnalysis
    timestamp: datetime
    report_text: Optional[str]

def generate_seo_report(url: str, content: ContentAnalysis, technical: TechnicalAnalysis, 
                       meta: MetaAnalysis, images: ImageAnalysis, timestamp: datetime) -> str:
    score = calculate_seo_score(content, technical, meta, images)
    
    return f"""# SEO Analysis Report for {url}
Generated: {timestamp}
Overall Score: {score}/100

## Critical Issues
{generate_critical_issues(content, technical, meta, images)}

## Technical Analysis
- Load Time: {technical.load_time:.2f}s {'🔴' if technical.load_time > 3 else '🟢'}
- Mobile Friendly: {'🟢 Yes' if technical.mobile_friendly else '🔴 No'}
- SSL: {'🟢 Valid' if 'error' not in technical.ssl_info else '🔴 Invalid'}
- Domain Age: {technical.domain_age} days

## Content Analysis
- Words: {content.word_count} {'🟢' if content.word_count > 300 else '🔴'}
- Reading Score: {content.readability_score:.1f}
- Internal Links: {len(content.internal_links)}
- External Links: {len(content.external_links)}
- Broken Links: {len(content.broken_links)}

## Meta Tags
- Title ({meta.title_length}/60): {meta.title}
- Description ({meta.meta_description_length}/160): {meta.meta_description}
- OG Tags: {len(meta.og_tags)}
- Twitter Cards: {len(meta.twitter_tags)}

## Images
- Total: {images.total_images}
- Missing Alt: {len(images.images_without_alt)}
- Large Images: {len(images.large_images)}

## Recommendations
{generate_recommendations(content, technical, meta, images)}"""

def calculate_seo_score(content: ContentAnalysis, technical: TechnicalAnalysis, 
                       meta: MetaAnalysis, images: ImageAnalysis) -> int:
    score = 100
    deductions = {
        'load_time': 15 if technical.load_time > 3 else 0,
        'mobile_friendly': 10 if not technical.mobile_friendly else 0,
        'ssl': 10 if 'error' in technical.ssl_info else 0,
        'word_count': 10 if content.word_count < 300 else 0,
        'meta_desc': 5 if not meta.meta_description else 0,
        'broken_links': 5 if content.broken_links else 0,
        'missing_alts': 5 if images.images_without_alt else 0
    }
    return max(0, score - sum(deductions.values()))

def generate_critical_issues(content: ContentAnalysis, technical: TechnicalAnalysis, 
                           meta: MetaAnalysis, images: ImageAnalysis) -> str:
    issues = []
    if technical.load_time > 3:
        issues.append("- Slow page load (>3s)")
    if not technical.mobile_friendly:
        issues.append("- Not mobile-friendly")
    if content.broken_links:
        issues.append("- Broken links detected")
    if len(images.images_without_alt) > 0:
        issues.append("- Images missing alt text")
    return "\n".join(issues) if issues else "No critical issues found"

def generate_recommendations(content: ContentAnalysis, technical: TechnicalAnalysis, 
                           meta: MetaAnalysis, images: ImageAnalysis) -> str:
    recs = []
    if technical.load_time > 3:
        recs.append("1. Optimize page speed:\n   - Compress images\n   - Minimize CSS/JS\n   - Enable caching")
    if not technical.mobile_friendly:
        recs.append("2. Implement responsive design")
    if content.word_count < 300:
        recs.append("3. Add more quality content")
    if images.images_without_alt:
        recs.append("4. Add alt text to images")
    return "\n\n".join(recs) if recs else "No major improvements needed"

@app.post("/analyze", response_model=SEOReport)
async def analyze_url(url_input: URLInput):
    try:
        response = requests.get(url_input.url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        content = analyze_content(soup, url_input.url)
        technical = analyze_technical(url_input.url)
        meta = analyze_meta(soup)
        images = analyze_images(soup, url_input.url)
        timestamp = datetime.now()
        
        report_text = generate_seo_report(
            url_input.url, content, technical, meta, images, timestamp
        )
        
        return SEOReport(
            url=url_input.url,
            content=content,
            technical=technical,
            meta=meta,
            images=images,
            timestamp=timestamp,
            report_text=report_text
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
def analyze_content(soup, url) -> ContentAnalysis:
    text = ' '.join([text for text in soup.stripped_strings])
    words = text.split()
    
    # Analyze headings
    heading_structure = {}
    for i in range(1, 7):
        tags = soup.find_all(f'h{i}')
        heading_structure[f'h{i}'] = [tag.get_text().strip() for tag in tags]
    
    # Analyze links
    internal_links = []
    external_links = []
    broken_links = []
    domain = urlparse(url).netloc
    
    for link in soup.find_all('a', href=True):
        href = link['href']
        if domain in href:
            internal_links.append(href)
        else:
            external_links.append(href)
            try:
                response = requests.head(href, timeout=5)
                if response.status_code >= 400:
                    broken_links.append(href)
            except:
                broken_links.append(href)
    
    return ContentAnalysis(
        word_count=len(words),
        keyword_density=calculate_keyword_density(text),
        readability_score=calculate_readability(text),
        text_html_ratio=len(text) / len(str(soup)),
        heading_structure=heading_structure,
        internal_links=internal_links,
        external_links=external_links,
        broken_links=broken_links
    )

def analyze_technical(url) -> TechnicalAnalysis:
    start_time = time.time()
    response = requests.get(url)
    load_time = time.time() - start_time
    
    domain = urlparse(url).netloc
    
    # SSL Check
    ssl_info = {}
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443)) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                ssl_info = {
                    'version': ssock.version(),
                    'expiry': ssock.getpeercert()['notAfter']
                }
    except:
        ssl_info = {'error': 'SSL certificate issue detected'}
    
    # Robots.txt
    robots_info = {}
    try:
        rerp = RobotExclusionRulesParser()
        rerp.fetch(f'https://{domain}/robots.txt')
        robots_info = {
            'exists': True,
            'allowed': rerp.is_allowed("*", "/"),
            'crawl_delay': rerp.get_crawl_delay("*")
        }
    except:
        robots_info = {'exists': False}    
    # Domain age
    domain_age = None
    try:
        w = whois.whois(domain)
        if w.creation_date:
            if isinstance(w.creation_date, list):
                domain_age = (datetime.now() - w.creation_date[0]).days
            else:
                domain_age = (datetime.now() - w.creation_date).days
    except:
        pass
    
    return TechnicalAnalysis(
        load_time=load_time,
        page_size=len(response.content),
        ssl_info=ssl_info,
        mobile_friendly=check_mobile_friendly(response.text),
        robots_txt=robots_info,
        sitemap_status=check_sitemap(domain),
        domain_age=domain_age,
        server_info={
            'server': response.headers.get('server'),
            'powered_by': response.headers.get('x-powered-by')
        }
    )

def analyze_meta(soup) -> MetaAnalysis:
    og_tags = {}
    twitter_tags = {}
    
    for meta in soup.find_all('meta'):
        if meta.get('property', '').startswith('og:'):
            og_tags[meta['property']] = meta.get('content')
        if meta.get('name', '').startswith('twitter:'):
            twitter_tags[meta['name']] = meta.get('content')
    
    return MetaAnalysis(
        title=soup.title.string if soup.title else "",
        title_length=len(soup.title.string) if soup.title else 0,
        meta_description=soup.find('meta', {'name': 'description'}).get('content', '') if soup.find('meta', {'name': 'description'}) else '',
        meta_description_length=len(soup.find('meta', {'name': 'description'}).get('content', '')) if soup.find('meta', {'name': 'description'}) else 0,
        meta_keywords=[keyword.strip() for keyword in soup.find('meta', {'name': 'keywords'}).get('content', '').split(',')] if soup.find('meta', {'name': 'keywords'}) else [],
        canonical_url=soup.find('link', {'rel': 'canonical'}).get('href') if soup.find('link', {'rel': 'canonical'}) else None,
        og_tags=og_tags,
        twitter_tags=twitter_tags
    )

def analyze_images(soup, url) -> ImageAnalysis:
    images = soup.find_all('img')
    images_without_alt = []
    large_images = []
    image_formats = {}
    
    for img in images:
        src = img.get('src', '')
        if not src:
            continue
            
        if not img.get('alt'):
            images_without_alt.append(src)
        
        try:
            img_response = requests.head(src if src.startswith('http') else f"{url}/{src}")
            size = int(img_response.headers.get('content-length', 0))
            if size > 100000:  # Images larger than 100KB
                large_images.append({
                    'src': src,
                    'size': size
                })
            
            format = img_response.headers.get('content-type', '').split('/')[-1]
            image_formats[format] = image_formats.get(format, 0) + 1
        except:
            continue
    
    return ImageAnalysis(
        total_images=len(images),
        images_without_alt=images_without_alt,
        large_images=large_images,
        image_formats=image_formats
    )

# Helper functions
def calculate_readability(text):
    # Implement Flesch Reading Ease Score
    sentences = len(re.split(r'[.!?]+', text))
    words = len(text.split())
    syllables = sum([count_syllables(word) for word in text.split()])
    if sentences == 0 or words == 0:
        return 0
    return 206.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words)

def count_syllables(word):
    # Basic syllable counting
    word = word.lower()
    count = 0
    vowels = "aeiouy"
    if word[0] in vowels:
        count += 1
    for index in range(1, len(word)):
        if word[index] in vowels and word[index-1] not in vowels:
            count += 1
    if word.endswith("e"):
        count -= 1
    if count == 0:
        count += 1
    return count

def check_mobile_friendly(html):
    # Basic mobile-friendly checks
    soup = BeautifulSoup(html, 'html.parser')
    viewport = soup.find('meta', {'name': 'viewport'})
    return viewport is not None

def check_sitemap(domain):
    sitemap_status = {}
    common_paths = ['/sitemap.xml', '/sitemap_index.xml']
    
    for path in common_paths:
        try:
            response = requests.get(f'https://{domain}{path}')
            if response.status_code == 200:
                sitemap_status[path] = 'Found'
            else:
                sitemap_status[path] = 'Not found'
        except:
            sitemap_status[path] = 'Error checking'
    
    return sitemap_status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)