# Opening Bell Daily

<img width="1200" alt="CleanShot 2025-10-07 at 23 03 05@2x" src="https://github.com/user-attachments/assets/5cf487f0-25b7-4c4c-a251-bc6b906f25d2" />

Add to your OpenBB workspace by going to [https://pro.openbb.co/](https://pro.openbb.co/), clicking on "Apps" and clicking "Connect Backend".

For endpoint URL you can use https://openbb-opening-bell-daily.fly.dev which I'm hosting personally.

Then you will want to add a Authentication for access to FRED.
- Key should be: X-FRED-API-KEY
- Value should be get from here: https://fred.stlouisfed.org/docs/api/api_key.html

Something like this:

<img width="600" alt="CleanShot 2025-10-07 at 23 00 50@2x" src="https://github.com/user-attachments/assets/8afcd4e7-41bf-4390-b8ac-645cf308af1a" />

---

Instead of utilizing my hosted app, you can run this locally with

```bash
uvicorn main:app --port 8080
```

and update the endpoint URL to utilize http://127.0.0.1:8080
