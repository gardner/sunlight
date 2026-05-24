export default {
  async fetch(request: Request, env: { AI: any }) {
    if (request.method === "GET") {
      return Response.json(await env.AI.toMarkdown().supported());
    }

    if (request.method !== "POST") {
      return Response.json({ error: "Method not allowed" }, { status: 405 });
    }

    const form = await request.formData();
    const files = form.getAll("files").filter((value): value is File => value instanceof File);
    if (files.length === 0) {
      return Response.json({ error: "No files uploaded" }, { status: 400 });
    }

    const conversionOptions = parseConversionOptions(form.get("conversionOptions"));
    const documents = files.map((file) => ({
      name: file.name,
      blob: file,
    }));
    const result = await env.AI.toMarkdown(documents, { conversionOptions });
    return Response.json(result);
  },
};

function parseConversionOptions(value: FormDataEntryValue | null) {
  if (typeof value !== "string" || value.trim() === "") {
    return {};
  }
  return JSON.parse(value);
}
