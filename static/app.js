async function loadStatus() {
    try {
        const response = await fetch(
            '/api/status',
            {
                cache: 'no-store'
            }
        );

        const data = await response.json();

        const container =
            document.getElementById('systems');

        container.innerHTML = '';

        for (const check of data.checks) {
            const element =
                document.createElement('div');

            element.className =
                `system ${check.status}`;

            let details = [];

            if (check.http_status !== undefined) {
                details.push(
                    `HTTP ${check.http_status}`
                );
            }

            if (check.response_ms !== undefined) {
                details.push(
                    `${check.response_ms} ms`
                );
            }

            if (check.error) {
                details.push(check.error);
            }

            element.innerHTML = `
                <div class="name">
                    ${escapeHtml(check.name)}
                </div>

                <div class="description">
                    ${escapeHtml(
                        check.description || ''
                    )}
                </div>

                <div class="details">
                    ${escapeHtml(
                        details.join(' | ')
                    )}
                </div>

                <div class="state">
                    ${check.status.toUpperCase()}
                </div>
            `;

            container.appendChild(element);
        }

        if (data.generated) {
            const date =
                new Date(data.generated);

            document.getElementById(
                'last-update'
            ).textContent =
                'Letzte Prüfung: ' +
                date.toLocaleString();
        }

    } catch (error) {
        document.getElementById(
            'last-update'
        ).textContent =
            'Status konnte nicht geladen werden';
    }
}


function escapeHtml(value) {
    const div =
        document.createElement('div');

    div.textContent = value;

    return div.innerHTML;
}


loadStatus();

setInterval(
    loadStatus,
    5000
);
