/** Native private File upload; expense posting remains a separate confirmed command. */
export async function uploadExpenseReceipt(file: File): Promise<string> {
	const data = new FormData();
	data.append("file", file);
	data.append("is_private", "1");
	const response = await fetch("/api/method/upload_file", {
		method: "POST",
		credentials: "same-origin",
		headers: { "X-Frappe-CSRF-Token": (window as any).frappe.csrf_token },
		body: data,
	});
	const result = await response.json();
	const url = result.message?.file_url;
	if (
		!response.ok ||
		typeof url !== "string" ||
		!url.startsWith("/private/files/")
	) {
		throw new Error(
			(window.__ || ((text: string) => text))(
				"Receipt upload failed. Your expense has not been submitted.",
			),
		);
	}
	return url;
}

export function receiptUrl(url: unknown): string | undefined {
	return typeof url === "string" &&
		/^\/(private\/)?files\/[^\\\r\n]+$/.test(url)
		? url
		: undefined;
}
