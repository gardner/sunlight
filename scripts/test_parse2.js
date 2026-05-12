import PostalMime from 'postal-mime';
import { readFileSync } from 'fs';

async function main() {
  const buf = readFileSync('test.eml'); // Returns a Buffer, which is a Uint8Array
  const parser = new PostalMime();
  const email = await parser.parse(buf);
  console.log("Text length:", email.text ? email.text.length : 0);
  console.log("HTML length:", email.html ? email.html.length : 0);
  console.log("Subject:", email.subject);
}
main();
