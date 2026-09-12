"""Browser verification and visual captures for the standalone landing page."""
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:5174/'
OUT = Path(__file__).resolve().parents[1] / 'tmp/qa'
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':1440,'height':1000}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until='networkidle')
    page.wait_for_timeout(2200)
    page.screenshot(path=str(OUT / 'desktop-hero.png'))
    assert not page.evaluate('Array.from(document.images).filter(i=>i.complete && !i.naturalWidth).length'), 'Broken image'
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), 'Desktop horizontal overflow'
    for selector, name in [('#how','how'),('#campaigns','campaigns'),('#earnings','calculator'),('#proof','proof'),('#brands','brands'),('#faq','faq')]:
        page.locator(selector).scroll_into_view_if_needed()
        page.wait_for_timeout(260)
        page.screenshot(path=str(OUT / (name+'-entrance.png')))
        page.wait_for_timeout(1800)
        page.locator(selector).screenshot(path=str(OUT / (name+'.png')))
        assert page.locator(selector).evaluate('(el)=>el.getAnimations({subtree:true}).filter(a=>a.playState==="running").length') == 0, f'Entrance did not settle: {name}'
    page.locator('[data-filter="music"]').click()
    assert page.locator('.campaign-card:visible').count() == 1
    page.locator('[data-campaign="music"]').click()
    assert page.locator('#detailDialog').is_visible()
    page.screenshot(path=str(OUT / 'brief-dialog.png'))
    page.locator('#tryRate').click()
    assert page.locator('#rateSelect').input_value() == '850'
    assert page.locator('#calcMoney').inner_text() == '₦42,500'
    page.locator('#viewSlider').fill('128000')
    assert page.locator('#calcMoney').inner_text() == '₦108,800'
    page.locator('#viewSlider').fill('0')
    assert page.locator('#calcMoney').inner_text() == '₦0'
    page.locator('#viewSlider').fill('500000')
    assert page.locator('#calcMoney').inner_text() == '₦425,000'
    page.locator('#rateSelect').select_option('500')
    page.locator('#viewSlider').fill('50000')
    page.locator('[data-filter="all"]').click()
    assert page.locator('.campaign-card:visible').count() == 3
    page.locator('.brands-copy [data-open="brand"]').click()
    page.locator('#briefName').fill('The next Lagos anthem')
    page.locator('#briefBudget').fill('100000')
    assert '200,000' in page.locator('#briefReach').inner_text()
    page.locator('#briefChecklist').fill('Use the campaign sound.\nTag the artist.')
    with page.expect_download() as download:
        page.locator('#brandForm button').click()
    download.value.save_as(str(OUT / 'sample-brief.txt'))
    page.screenshot(path=str(OUT / 'brand-dialog.png'))
    page.keyboard.press('Escape')
    assert not page.locator('#detailDialog').is_visible()
    page.locator('summary').filter(has_text='How are my earnings').click()
    assert page.locator('details[open]').filter(has_text='How are my earnings').count() == 1
    page.locator('#join').evaluate('(el)=>window.scrollTo({top:el.offsetTop,behavior:"instant"})')
    page.wait_for_timeout(2000)
    page.screenshot(path=str(OUT / 'throw-start.png'))
    page.locator('#join').evaluate('(el)=>window.scrollTo({top:el.offsetTop+(el.offsetHeight-innerHeight)*.38,behavior:"instant"})')
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / 'throw-mid.png'))
    page.locator('#join').evaluate('(el)=>window.scrollTo({top:el.offsetTop+el.offsetHeight-innerHeight,behavior:"instant"})')
    page.wait_for_timeout(900)
    page.screenshot(path=str(OUT / 'finale.png'))
    assert not page.locator('#phone').evaluate('(el)=>el.inert')
    page.locator('#celebrate').click()
    page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / 'confetti.png'))
    for width in [390,768,1024,1920,320]:
        page.set_viewport_size({'width':width,'height':844 if width<700 else 1000})
        page.evaluate('window.scrollTo({top:0,behavior:"instant"})')
        page.wait_for_timeout(500)
        overflow = page.evaluate('document.documentElement.scrollWidth > innerWidth')
        print('Viewport', width, 'overflow', overflow)
        assert not overflow, f'Horizontal overflow at {width}px'
        page.screenshot(path=str(OUT / f'hero-{width}.png'))
        if width == 390:
            page.locator('#burger').click()
            assert page.locator('#mobileNav').is_visible()
            page.locator('#mobileNav a[href="#campaigns"]').click()
            assert not page.locator('#mobileNav').is_visible()
            page.wait_for_timeout(1200)
            page.locator('#campaigns').screenshot(path=str(OUT / 'mobile-campaigns.png'))
            page.locator('#earnings').scroll_into_view_if_needed()
            page.screenshot(path=str(OUT / 'mobile-calculator.png'))
            page.locator('#join').evaluate('(el)=>window.scrollTo({top:el.offsetTop+el.offsetHeight-innerHeight,behavior:"instant"})')
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / 'mobile-finale.png'))
    print('Errors', errors)
    assert not page.evaluate('Array.from(document.images).filter(i=>!i.complete || !i.naturalWidth).length'), 'Missing image after scrolling'
    reduced = browser.new_page(viewport={'width':390,'height':844}, reduced_motion='reduce')
    reduced.goto(BASE, wait_until='networkidle')
    assert not reduced.locator('#join').evaluate('(el)=>el.classList.contains("throw-enabled")')
    assert not reduced.locator('#phone').evaluate('(el)=>el.inert')
    reduced.locator('#join').scroll_into_view_if_needed()
    reduced.screenshot(path=str(OUT / 'reduced-finale.png'))
    # Changing motion preference mid-entrance must reveal the content immediately.
    motion = browser.new_page(viewport={'width':390,'height':844})
    motion.goto(BASE, wait_until='networkidle')
    motion.locator('.campaign-card').first.scroll_into_view_if_needed()
    motion.wait_for_timeout(150)
    motion.screenshot(path=str(OUT / 'mobile-card-entrance.png'))
    motion.emulate_media(reduced_motion='reduce')
    motion.wait_for_timeout(100)
    assert motion.locator('.campaign-card').first.evaluate('(el)=>getComputedStyle(el).opacity') == '1'
    assert motion.locator('#campaigns').evaluate('(el)=>el.getAnimations({subtree:true}).length') == 0
    motion.screenshot(path=str(OUT / 'motion-preference-change.png'))
    motion.close()
    nojs = browser.new_page(viewport={'width':1440,'height':1000}, java_script_enabled=False)
    nojs.goto(BASE, wait_until='networkidle')
    assert nojs.locator('h1').is_visible()
    assert nojs.locator('#phoneContent').is_visible()
    browser.close()
    assert not errors, errors
    print('PASS: calculator, filters, briefs, downloads, mobile navigation, finale, reduced motion, no-JS content.')
