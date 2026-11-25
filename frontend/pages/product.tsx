import Head from "next/head";
import TripPlanner from "../components/TripPlanner";

export default function Product() {
  return (
    <>
      <Head>
        <title>
          Trip Planner — TripCraft AI
        </title>
      </Head>

      <TripPlanner />
    </>
  );
}
