import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.CMK_BACKEND_URL || "http://localhost:7749";

export async function POST(request: NextRequest) {
  const authHeader = request.headers.get("authorization");
  if (!authHeader) {
    return NextResponse.json({ error: "missing authorization" }, { status: 401 });
  }

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid json" }, { status: 400 });
  }

  try {
    const resp = await fetch(`${BACKEND_URL}/api/v1/synthesize`, {
      method: "POST",
      headers: {
        "Authorization": authHeader,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await resp.json();
    return NextResponse.json(data, { status: resp.status });
  } catch (e) {
    return NextResponse.json(
      { error: "backend unavailable" },
      { status: 502 },
    );
  }
}
