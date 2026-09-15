import { queueRequest } from "@/lib/loop/http";
export const dynamic = "force-dynamic";
export const GET = (request: Request) => queueRequest(request, "GET");
export const POST = (request: Request) => queueRequest(request, "POST");
