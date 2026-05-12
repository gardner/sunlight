import PostalMime from 'postal-mime';

async function main() {
  const rawEmail = `From: Test <test@example.com>\r\nTo: reply-123@sunlight.nz\r\nSubject: Re: Official Information request\r\nContent-Type: text/plain; charset="utf-8"\r\n\r\nThis is a 2nd response.\r\n`;
  const parser = new PostalMime();
  const email = await parser.parse(rawEmail);
  console.log("Text:", email.text);
  console.log("HTML:", email.html);
}
main();