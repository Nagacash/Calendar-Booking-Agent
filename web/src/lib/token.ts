import { SignJWT } from "jose";

/** Mint a LiveKit access token in the browser from the user's own API secret (BYOK). */
export async function mintLiveKitToken(opts: {
  apiKey: string;
  apiSecret: string;
  identity: string;
  name: string;
  roomName: string;
  agentName: string;
}): Promise<string> {
  const secret = new TextEncoder().encode(opts.apiSecret);
  const now = Math.floor(Date.now() / 1000);

  return new SignJWT({
    name: opts.name,
    video: {
      roomJoin: true,
      room: opts.roomName,
      canPublish: true,
      canSubscribe: true,
      canPublishData: true,
    },
    roomConfig: {
      agents: [{ agentName: opts.agentName }],
    },
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuer(opts.apiKey)
    .setSubject(opts.identity)
    .setNotBefore(now)
    .setExpirationTime(now + 60 * 60 * 6)
    .sign(secret);
}
