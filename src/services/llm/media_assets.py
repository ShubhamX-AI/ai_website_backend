"""
Media Asset Map for Indus Net Technologies
This file maps semantic asset keys to their corresponding URLs.
mediaType and aspectRatio are intentionally omitted — the frontend resolves these intelligently.
"""
from typing import Dict, Any

MEDIA_ASSETS: Dict[str, Dict[str, Any]] = {
    # IMAGES
    "indus_office": {
        "urls": ["https://media.licdn.com/dms/image/v2/D5622AQEXFMOWHG9UEQ/feedshare-shrink_800/B56Zoqi1FHG4Ag-/0/1761650367301?e=2147483647&v=beta&t=exXz0i4LcAqW6E3yIHlA7mggZvz4pE2X3OWWq4Eecmw"],
    },
    # Kolkata Newtown (Ecospace) office. "kolkata_office" kept as a generic
    # alias for back-compat; it points to the same Newtown image.
    "kolkata_newtown_office": {
        "urls": ["https://intglobal.com/wp-content/uploads/2025/06/image-134.webp"],
    },
    "kolkata_office": {
        "urls": ["https://intglobal.com/wp-content/uploads/2025/06/image-134.webp"],
    },
    # Kolkata Sector 5 (SDF Building) office.
    "kolkata_sector5_office": {
        "urls": ["https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgBP_TLtUJMWc8xyC8r2b1pTCbaOP4kALPPdr7x44Ts12WNfv4XPtmkDsUmSeJ9M4HOnf6ApIn_CZE4Gs7I3zCpL2m0fbPoaKAt8UcBwT2zoAGWuD0gqp4GebqFvfuCwvzTae-v13u3KhU/s1600/DSCN0274.JPG"],
    },
    "ceo_abhishek_rungta": {
        "urls": ["https://intglobal.com/wp-content/uploads/2025/12/AR-Image-scaled-1.webp"],
    },
    "abhishek_rungta_sign": {
        "urls": ["https://intglobal.com/wp-content/uploads/2025/01/Abhishek-Rungta-1.png"],
    },
    "contact": {
        "urls": ["https://intglobal.com/wp-content/uploads/2025/01/image-1226x1511-1.png"],
    },
    "customer_experience": {
        "urls": ["https://www.gosurvey.in/media/a0vmcbf1/customer-experience-is-important-for-businesses.jpg"],
    },
    "ai_analytics": {
        "urls": ["https://www.gooddata.com/img/blog/_1200x630/what-is-ai-analytics_cover.png.webp"],
    },
    "cybersecurity": {
        "urls": ["https://www.dataguard.com/hubfs/240326_Blogpost_CybersecurityMeasures%20(1).webp"],
    },
    "global_map": {
        "urls": ["https://i.pinimg.com/564x/4e/9f/64/4e9f64e490a5fa034082d107ecbb5faf.jpg"],
    },

    # VIDEOS
    "intro_video": {
        "urls": ["https://youtu.be/iOvGVR7Lo_A?si=p8j8c72qXh-wpm4Z"],
    },
    "ceo_video": {
        "urls": ["https://intglobal.com/wp-content/uploads/2025/06/Abhishek-Rungta-INT-Intro.mp4"],
    },
    "careers_video": {
        "urls": ["https://www.youtube.com/watch?v=1pk9N_yS3lU&t=12s"],
    },
}
