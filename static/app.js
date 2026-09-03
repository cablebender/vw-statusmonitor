async function loadStatus() {
    const lastUpdate =
        document.getElementById(
            'last-update'
        );

    const container =
        document.getElementById(
            'systems'
        );

    try {
        const response = await fetch(
            '/api/status',
            {
                cache: 'no-store'
            }
        );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const data =
            await response.json();

        container.innerHTML = '';

        for (const check of data.checks) {
            const element =
                document.createElement(
                    'div'
                );

            const status =
                [
                    'up',
                    'down',
                    'unknown'
                ].includes(check.status)
                    ? check.status
                    : 'unknown';

            element.className =
                `system ${status}`;

            const details = [];

            if (
                check.http_status
                !== undefined
            ) {
                details.push(
                    `HTTP ${check.http_status}`
                );
            }

            if (
                check.response_ms
                !== undefined
            ) {
                details.push(
                    `${check.response_ms} ms`
                );
            }

            if (check.port !== undefined) {
                details.push(
                    `Port ${check.port}`
                );
            }

            if (check.error) {
                details.push(
                    check.error
                );
            }

            element.innerHTML = `
                <div class="name">
                    ${escapeHtml(
                        check.name
                    )}
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
                    ${status.toUpperCase()}
                </div>
            `;

            container.appendChild(
                element
            );
        }

        if (data.generated) {
            const date =
                new Date(
                    data.generated
                );

            lastUpdate.textContent =
                'Letzte Prüfung: '
                + date.toLocaleString();

        } else {
            lastUpdate.textContent =
                'Noch keine Prüfung durchgeführt';
        }

    } catch (error) {
        lastUpdate.textContent =
            'Status konnte nicht geladen werden';

        console.error(
            'Status request failed:',
            error
        );
    }
}


function escapeHtml(value) {
    const div =
        document.createElement(
            'div'
        );

    div.textContent =
        String(value ?? '');

    return div.innerHTML;
}


loadStatus();

setInterval(
    loadStatus,
    5000
);
