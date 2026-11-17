// only for VS Code: tells the editor what Deno and the npm: import are
declare const Deno: {
  env: { get(key: string): string | undefined };
  serve(handler: (req: Request) => Response | Promise<Response>): unknown;
};

declare module "npm:@supabase/supabase-js@2" {
  // deno-lint-ignore no-explicit-any
  export function createClient(url: string, key: string, options?: unknown): any;
}

interface ImportMeta {
  main: boolean;
}
