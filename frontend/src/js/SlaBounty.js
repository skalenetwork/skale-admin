import React from 'react'
import SlaBountyList from './SlaBountyList'
import PageTitle from "./shared_components/PageTitle";

export default class SlaBounty extends React.Component {

    _isMounted = false;

    constructor(props) {
        super(props);
        this.state = {
            loaded: false,

        };

        this.getLogsList = this.getLogsList.bind(this)
    }


    componentDidMount() {
        this._isMounted = true;
        if (this._isMounted) {
            this.getLogsList();
            this.interval = setInterval(() => {
                this.getLogsList()
            }, 25000)
        }
    }

    componentWillUnmount() {
        this._isMounted = false;
        clearInterval(this.interval);
    }

    getLogsList() {
        const url = '/bounty-info';
        let self = this;
        fetch(url)
            .then((resp) => resp.json())
            .then(function (data) {
                console.log('data', data);

                if (data.errors) {
                    let errorPath = constructErrorPath(data.errors[0].msg);
                }

                if (self._isMounted) {
                    self.setState({
                        logs: data.data.events,
                        loaded: true
                    });
                }
            })
            .catch(function (error) {
                console.log(error);
            });
    }


    render() {
        return (
            <div className="marg-30">
                <div className="padd-left-sm">
                    <PageTitle
                        title={'SLA/Bounty '}
                    />
                </div>
                <SlaBountyList darkMode={this.props.darkMode}
                               loaded={this.state.loaded}
                               logs={this.state.logs}
                />
            </div>
        )
    }
}
