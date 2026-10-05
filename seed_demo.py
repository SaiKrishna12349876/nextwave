"""Seed realistic demo data so the dashboard looks alive in the video. Run: python seed_demo.py"""
import random, sqlite3, os
from datetime import datetime, timedelta
from app import init_db, DB_PATH, make_code, app
random.seed(7)
first=["Priya","Rahul","Sneha","Arjun","Divya","Karthik","Meghana","Vikram","Anjali","Sai","Harsha","Lakshmi","Nikhil","Pooja","Ravi","Tejaswi","Manoj","Keerthi","Aditya","Bhavana"]
last=["Sharma","Reddy","Kumar","Naidu","Rao","Varma","Patel","Chowdary","Iyer","Gupta"]
colleges=["Amrita Amaravati","VIT-AP","SRM AP","KL University","VVIT Guntur","RVR&JC Guntur","GITAM Vizag","VNR VJIET","CBIT Hyderabad","Andhra University"]
src_w={"wa":55,"ref":0,"li":12,"club":10,"email":18,"qr":5}
init_db()
with app.app_context():
    from app import db
    c=db(); codes=[]; start=datetime.utcnow()-timedelta(days=6)
    for i in range(320):
        name=f"{random.choice(first)} {random.choice(last)}"; code=make_code(name)
        ref=random.choice(codes) if codes and random.random()<0.32 else None
        src="ref" if ref else random.choices(list(src_w),weights=list(src_w.values()))[0]
        day=min(6,int(random.triangular(0,7,4.5))); ts=start+timedelta(days=day,hours=random.randint(8,22))
        try:
            c.execute("INSERT INTO registrations(code,name,college,branch,whatsapp,email,referrer_code,source,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                      (code,name,random.choice(colleges),random.choice(["CSE","IT","ECE","AI/ML / DS"]),f"91{random.randint(6000000000,9999999999)}","",ref,src,ts.isoformat()))
            codes.append(code)
        except sqlite3.IntegrityError: pass
    c.commit(); print("seeded", len(codes), "rows into", DB_PATH)
