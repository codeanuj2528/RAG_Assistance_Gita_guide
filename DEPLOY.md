# Krishna Voice Assistant - Render Deployment

## Quick Deploy to Render (FREE)

### Step 1: Push to GitHub
```bash
git add .
git commit -m "Add deployment files"
git push origin main
```

### Step 2: Deploy on Render
1. Go to [render.com](https://render.com)
2. Sign in with GitHub
3. Click **"New"** → **"Web Service"**
4. Connect repository: `codeanuj2528/RAG_Assistance_Gita_guide`
5. Set **Root Directory**: `Krishna_Voice`
6. Select **Free** plan
7. Add Environment Variables:
   - `OPENAI_API_KEY` = your key
   - `GROQ_API_KEY` = your key
   - `ELEVENLABS_API_KEY` = your key (optional)
8. Click **"Create Web Service"**

### Step 3: Access Your App
After ~5 min build, you'll get:  
`https://krishna-voice.onrender.com`

## Notes
- Free tier sleeps after 15 min idle (wakes in ~30s)
- 750 free hours/month
- Auto-renews monthly
