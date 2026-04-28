document.addEventListener("DOMContentLoaded", () => {
  const links = document.querySelectorAll(".nav a");

  links.forEach(link => {
    link.addEventListener("click", () => {
      links.forEach(x => x.classList.remove("active"));
      link.classList.add("active");
    });
  });

  const flashes = document.querySelectorAll(".flash");
  if (flashes.length) {
    setTimeout(() => {
      flashes.forEach(f => {
        f.style.opacity = "0";
        f.style.transform = "translateY(-8px)";
      });
    }, 2200);
  }
});

async function loadVisitNote(medicineId) {
  const box = document.getElementById("visit-note");
  box.innerText = "正在生成复诊沟通话术……";

  try {
    const res = await fetch(`/api/visit_note/${medicineId}`);
    const data = await res.json();

    if (data.note) {
      box.innerText = data.note;
    } else {
      box.innerText = "生成失败，请稍后重试。";
    }
  } catch (e) {
    box.innerText = "网络异常，无法生成话术。";
  }
}
