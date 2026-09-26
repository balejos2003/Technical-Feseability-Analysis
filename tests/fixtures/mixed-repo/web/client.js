export function fetchRecord(id) {
  return fetch(`/records/${id}`).then((response) => response.json());
}
