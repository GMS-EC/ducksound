import axios from "axios";

const client = axios.create({
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

export default client;
