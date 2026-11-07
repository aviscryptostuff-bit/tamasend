# TamaOS

Send your own wallpapers, toys, food and Gotchi Points to a Tamagotchi On / Meets over Bluetooth. You don't need the official app.

- **Phone (iPhone or Android):** `index.html`, a single web page.
- **PC (Windows):** `pc/tamaos_send.py`.
- **Ready-made items:** `items/` (pistol, skateboard, pizza, burger and the starter wallpaper).
- **Everything we've learned so far:** [HANDOFF.md](HANDOFF.md).

## Put the page online (one time)

1. On GitHub, open this repo and go to **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**. Pick **main** and **/ (root)**, then tap **Save**.
3. Wait a minute or two. The page will be at **https://aviscryptostuff-bit.github.io/tamasend/**.

## Send from iPhone

1. Install the **Bluefy** app from the App Store. Safari can't use Bluetooth.
2. Open the link above **in Bluefy**.
3. Check you have the new page. The top should say **+0 PTS**, and the coins box should say *"Sent along with the item. 0 to 99,999."*
4. On the Tama: **Connection → APP**, press back, then **Connection → Download**. The Tama's clock has to be set to daytime, because it won't connect while it's asleep.
5. On the page, pick an item, set the coins (try 50), and tap **Connect & send**. Choose **TMGC_meets**.
6. If it fails, tap **Copy log** and send a screenshot or the log text.

## Send from a PC

```
pip install bleak
python pc/tamaos_send.py items/wallpaper_bg50001.txt --points 50
```

Use `--delay 45` if the Tama's progress bar falls behind. Use `--dump out.bin` to build the message without sending it.
