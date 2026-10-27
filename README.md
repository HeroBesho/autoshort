# AutoShorts: free YouTube Shorts every 4 hours

Gemini writes the script, Pollinations draws the images, edge-tts speaks English,
FFmpeg builds the video, and the YouTube API uploads it. GitHub Actions runs it for free.

## Setup (one time)

### 1. Gemini key (free)
Go to https://aistudio.google.com/apikey and create an API key.

### 2. YouTube access
1. In Google Cloud (same project you made before is fine), enable **YouTube Data API v3**.
2. Credentials -> Create credentials -> OAuth client ID -> choose **Desktop app** (not Web application). Create it.
3. On the OAuth consent screen / Audience: add your Gmail as a Test user, then click **Publish app**
   (otherwise the login expires after 7 days).
4. On your computer run `python get_refresh_token.py`, paste the Client ID and Secret there,
   log in, and click Advanced -> Continue when Google warns the app is unverified.
   It prints a refresh token.

### 3. GitHub
1. Create a free account and a new repository (public is simplest: free unlimited Actions minutes).
2. Upload all the files in this folder, keeping the `.github/workflows/post.yml` path.
3. Repo -> Settings -> Secrets and variables -> Actions -> New repository secret. Add four:
   - `GEMINI_API_KEY`
   - `YT_CLIENT_ID`
   - `YT_CLIENT_SECRET`
   - `YT_REFRESH_TOKEN`
4. Repo -> Settings -> Actions -> General -> Workflow permissions -> **Read and write permissions**. Save.

### 4. Test
Actions tab -> "Post a YouTube Short" -> **Run workflow**. Wait a few minutes and check your channel.
Tip: to test safely first, change `PRIVACY: public` to `PRIVACY: private` in `post.yml`.
If it works, switch back to `public`. After that it runs every 4 hours by itself.

## Things to know
- If your videos show up as private, Google is restricting uploads from unaudited API projects.
  Check the current YouTube API rules.
- Default quota is 10,000 units/day and one upload costs about 1,600, so 6 uploads/day (9,600) fits
  with almost no room for retries or tests.
- GitHub pauses scheduled runs on a public repo after 60 days with no repo activity. The bot's
  history commit counts, but if it stops, press "Enable workflow" in the Actions tab.
- Free AI services can rate-limit or change. Their limits may differ from when this was written.
- YouTube asks creators to disclose realistic AI-generated content. Check the setting in YouTube Studio.
- Change the topic with the `VIDEO_NICHE` variable in `main.py`, and the voice with `VOICE`
  (any edge-tts voice, e.g. `en-US-AriaNeural`).
- Never paste keys or secrets into chat or commit them to the repo.
