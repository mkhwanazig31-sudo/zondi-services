# zondi.py V5 - Full Auth: Register -> Login -> Dashboard
from flask import Flask, request, jsonify, session, redirect
import os, datetime, json
from pathlib import Path

app = Flask(__name__)
app.secret_key = "zondi-v5-secret"
Path("evidence").mkdir(exist_ok=True)
EVIDENCE_FILE = "evidence/data.json"
USERS_FILE = "evidence/users.json"

evidence = json.load(open(EVIDENCE_FILE)) if os.path.exists(EVIDENCE_FILE) else []
users = json.load(open(USERS_FILE)) if os.path.exists(USERS_FILE) else {"guard1":{"pass":"1234","role":"guard"},"client1":{"pass":"1234","role":"client"}}

def save_ev(): json.dump(evidence, open(EVIDENCE_FILE,"w"))
def save_users(): json.dump(users, open(USERS_FILE,"w"))

LOGIN_PAGE = """
<html><head><title>Zondi Login</title><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{background:#050a0f;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;font-family:Arial;color:white}
.box{background:#0f1a24;padding:30px;border-radius:16px;border:1px solid #00e5ff33;width:90%;max-width:360px;text-align:center}
input,select{width:100%;padding:14px;margin:7px 0;border-radius:10px;border:none;background:#1a2a3a;color:white;box-sizing:border-box}
.btn{width:100%;padding:14px;background:#00e5ff;color:black;font-weight:bold;border:none;border-radius:10px;margin-top:12px;cursor:pointer}
.btn2{width:100%;padding:12px;background:transparent;color:#00e5ff;border:1px solid #00e5ff;border-radius:10px;margin-top:8px;cursor:pointer}
.tab{display:flex;margin-bottom:15px} .tab div{flex:1;padding:10px;cursor:pointer;border-bottom:2px solid #333} .active{border-bottom:2px solid #00e5ff!important;color:#00e5ff}
small{color:#888;font-size:11px}</style></head>
<body>
<div class="box">
<h2 style="color:#00e5ff;margin:0">ZONDI SERVICES</h2><p style="margin:5px 0 15px 0;color:#aaa">Ga-Rankuwa Security</p>

<div class="tab"><div id="t1" class="active" onclick="showTab(1)">LOGIN</div><div id="t2" onclick="showTab(2)">REGISTER</div></div>

<div id="loginForm">
<input id="u" placeholder="Username">
<input id="p" type="password" placeholder="Password">
<button class="btn" onclick="doLogin()">LOGIN</button>
<p id="msg1" style="color:#f55;font-size:12px"></p>
<small>Demo: guard1/1234 | client1/1234</small>
</div>

<div id="regForm" style="display:none
