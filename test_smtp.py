import pytest
from aiosmtplib import SMTP

@pytest.mark.asyncio
async def test_smtp():
    smtp = SMTP(hostname="smtp.gmail.com", port=587, start_tls=False)
    await smtp.connect()
    await smtp.ehlo()
    await smtp.starttls()
    await smtp.ehlo()
    await smtp.login("maximuschampion2002@gmail.com", "mqyohjngeptgdpkv")
    await smtp.sendmail(
        "maximuschampion2002@gmail.com",
        ["maximuschampion2002@gmail.com"],
        "Subject: Test\n\nHello from async SMTP!"
    )
    await smtp.quit()
    print("Email sent!")
