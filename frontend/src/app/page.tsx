import HomeClient from "./HomeClient";
import HomeSSR from "./HomeSSR";

export const dynamic = "force-dynamic";

export default function Home() {
  return (
    <>
      <HomeClient />
      <HomeSSR />
    </>
  );
}
