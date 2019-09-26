import React from 'react'

import {
    DataTable,
    DataTableContent,
    DataTableHead,
    DataTableBody,
    DataTableHeadCell,
    DataTableRow,
} from '@rmwc/data-table';
import '@rmwc/data-table/data-table.css';
import SlaBountyItem from "./SlaBountyItem";
// for before logs load
import {LinearProgress} from '@rmwc/linear-progress';
import '@material/linear-progress/dist/mdc.linear-progress.css';
import {Tooltip} from 'reactstrap';


export default class SlaBountyList extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            sortDate: -1,
            search: '',
            value: '',
            tooltipOpenDate: false,
            tooltipOpenBounty: false,
            tooltipOpenLatency: false,
            tooltipOpenDowntime: false,
        };

        this.reset = this.reset.bind(this);
        this.toggle = this.toggle.bind(this);
    }

    /////////////////////////////

    reset() {
        this.setState({search: '', sortDate: null})

    };

    toggle(value) {
        if (value === 'Date') {
            this.setState({
                tooltipOpenDate: !this.state.tooltipOpenDate
            });
        }
        if (value === 'Bounty') {
            this.setState({
                tooltipOpenBounty: !this.state.tooltipOpenBounty
            });
        }
        if (value === 'Latency') {
            this.setState({
                tooltipOpenLatency: !this.state.tooltipOpenLatency
            });
        }
        if (value === 'Downtime') {
            this.setState({
                tooltipOpenDowntime: !this.state.tooltipOpenDowntime
            });
        }
    }

    render() {

        let itemss = this.props.logs || [];

        if (!this.props.loaded) {
            return (
                <LinearProgress determinate={false}/>
            )
        }

        if (itemss.length === 0) {
            return (
                <h6 className="padd-left-md">No Logs found</h6>
            )
        }

        const search = this.state.search;
        let items = itemss.filter(item => {
            return item['tx_dt'].toLowerCase().indexOf(search.toLowerCase()) !== -1
        });

        let created = this.state.sortDate;
        if (created === 1) {
            items = _.sortBy(items, 'tx_dt');
        } else if (created === -1) {
            items = _.sortBy(items, 'tx_dt').reverse();
        } else {
            items
        }

        //
        let rows =
            items.map((v, i) => (
                <SlaBountyItem darkMode={this.props.darkMode} v={v} key={i}/>
            ));

        return (
            <div className="new-card" style={{paddingTop: '0px'}}>
                {/*                <InputGroup>
                    <Input className="schain-search-input" type="text" placeholder="&#xF002; Browse by Log Name"
                           charSet="utf-8"
                           onChange={(name) => this.setState({search: name.target.value})}
                           value={this.state.search}/>
                    <Button className="btn-md" unelevated raised onClick={() => this.reset()}>
                        Clear
                    </Button>
                </InputGroup>*/}

                <DataTable>
                    <DataTableContent>
                        <DataTableHead>
                            <DataTableRow>
                                <DataTableHeadCell
                                    sort={this.state.sortDate || null}
                                    onSortChange={sortDate => {
                                        this.setState({sortDate});
                                        console.log(sortDate)
                                    }}

                                >
                                    <a id={"Tooltip" + 'Date'}>
                                        Date
                                    </a>
                                    <Tooltip placement="top" isOpen={this.state.tooltipOpenDate}
                                             target={"Tooltip" + 'Date'} toggle={() => this.toggle('Date')}>
                                        Transaction date
                                    </Tooltip>
                                </DataTableHeadCell>

                                <DataTableHeadCell>
                                    <a id={"Tooltip" + 'Bounty'}>
                                        Bounty
                                    </a>
                                    <Tooltip placement="top" isOpen={this.state.tooltipOpenBounty}
                                             target={"Tooltip" + 'Bounty'} toggle={() => this.toggle('Bounty')}>
                                        Received bounty, SKALE
                                    </Tooltip>
                                </DataTableHeadCell>

                                <DataTableHeadCell>
                                    <a id={"Tooltip" + 'Latency'}>
                                        Latency
                                    </a>
                                    <Tooltip placement="top" isOpen={this.state.tooltipOpenLatency}
                                             target={"Tooltip" + 'Latency'} toggle={() => this.toggle('Latency')}>
                                        Average ping latency, ms
                                    </Tooltip>
                                </DataTableHeadCell>

                                <DataTableHeadCell>
                                    <a id={"Tooltip" + 'Downtime'}>
                                        Downtime
                                    </a>
                                    <Tooltip placement="top" isOpen={this.state.tooltipOpenDowntime}
                                             target={"Tooltip" + 'Downtime'} toggle={() => this.toggle('Downtime')}>
                                        Total downtime, min
                                    </Tooltip>
                                </DataTableHeadCell>

                                <DataTableHeadCell>
                                    Gas used
                                </DataTableHeadCell>

                                <DataTableHeadCell>
                                    More
                                </DataTableHeadCell>

                            </DataTableRow>
                        </DataTableHead>
                        <DataTableBody>
                            {rows}
                        </DataTableBody>
                    </DataTableContent>
                </DataTable>
            </div>
        )

    }
}
